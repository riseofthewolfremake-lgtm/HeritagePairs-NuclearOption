"""Surface features of the B-25H v2 skin, evaluated per livery texel in 3D (seam-free).

compute(G) -> dict of compressed (K,) arrays:
  H        height in metres (panel seams, lap joints, rivets, fasteners, fabric ribs/pillowing)
  seam     0-1 groove coverage (for colour / AO darkening)
  rivet    0-1 rivet head coverage
  panel    0-1 random value per skin panel (tint variation)
  fabric   1 on doped-fabric control surfaces
  walk     1 on wing-root walkways
  wear     0-1 chipping likelihood (leading edges, walkways, hatch edges, cowl lip ...)
  chip     0-1 paint chipped to bare metal (shared by all liveries and by _m)
  upper    0-1 weight of the upper-surface colour (camouflage demarcation)
  antiglare, nac_inboard   masks for anti-glare panels
  exhaust  0-1 exhaust soot staining
  grime    0-1 dirt amount
  fade     0-1 low-frequency paint fade
  access   1 near access-panel outlines (for stencils / wear)
The structural layout is a plausible B-25 arrangement, not a rivet-accurate drawing.
"""
import math
import numpy as np
from tex_lib import (F32, nearest_station, periodic, bin_index, groove, dome, smoothstep, fbm, vnoise,
                     hash1, seg_dist, load_tile, tri_sample, sd_box)

TAU = 2 * math.pi

# heights (m)
SEAM_D, SEAM_W = 0.0008, 0.0045
MAJOR_D = 0.0011
RIV_H, RIV_R = 0.00035, 0.0048
STR_RIV_H = 0.00022


def wrap_dist(a, stations):
    """angular distance to the nearest of `stations` (radians), wrap-aware; plus index."""
    st = np.asarray(stations, F32)
    d = np.abs(((a[:, None] - st[None, :]) + math.pi) % TAU - math.pi)
    j = np.argmin(d, axis=1)
    return d[np.arange(len(a)), j], j


class Acc:
    def __init__(self, K):
        self.H = np.zeros(K, F32)
        self.seam = np.zeros(K, F32)
        self.rivet = np.zeros(K, F32)

    def add_seam(self, m, d, depth=SEAM_D, w=SEAM_W):
        g = groove(d, w, depth)
        self.H[m] += g
        self.seam[m] = np.maximum(self.seam[m], -g / depth * min(1.0, depth / SEAM_D))

    def add_step(self, m, sd, h=0.0004, w=0.003):
        self.H[m] += h * smoothstep(-w, w, sd)

    def add_rivets(self, m, d_row, t, spacing, h=RIV_H, r=RIV_R, offset=0.0, row_w=None):
        da = periodic(t, spacing, offset)
        d = np.sqrt(d_row * d_row + da * da)
        v = dome(d, r, h)
        self.H[m] += v
        self.rivet[m] = np.maximum(self.rivet[m], v / RIV_H)


def rect_outline(acc, m, u, v, u0, u1, v0, v1, depth=SEAM_D * 0.9, fast=0.06, out_access=None):
    """access panel outline (groove) with fasteners every `fast` m along the edges."""
    du = np.minimum(np.abs(u - u0), np.abs(u - u1))
    dv = np.minimum(np.abs(v - v0), np.abs(v - v1))
    inu = (u > u0 - 0.01) & (u < u1 + 0.01)
    inv = (v > v0 - 0.01) & (v < v1 + 0.01)
    d = np.where(inv, du, 1.0)
    d = np.minimum(d, np.where(inu, dv, 1.0))
    acc.add_seam(m, d, depth)
    # fasteners: 12 mm inside the outline
    ins = 0.012
    fu = np.where(inv, np.minimum(np.abs(u - (u0 + ins)), np.abs(u - (u1 - ins))), 1.0)
    fv = np.where(inu, np.minimum(np.abs(v - (v0 + ins)), np.abs(v - (v1 - ins))), 1.0)
    a = np.sqrt(fu ** 2 + periodic(v, fast, v0 + ins) ** 2)
    b = np.sqrt(fv ** 2 + periodic(u, fast, u0 + ins) ** 2)
    dd = np.minimum(a, b)
    # screw head: shallow dish with a ring
    ring = np.exp(-((dd - 0.0045) / 0.0018) ** 2) * 0.00025 - np.exp(-(dd / 0.0025) ** 2) * 0.00015
    acc.H[m] += ring.astype(F32)
    acc.rivet[m] = np.maximum(acc.rivet[m], np.clip(1 - dd / 0.006, 0, 1))
    if out_access is not None:
        out_access[m] = np.maximum(out_access[m], np.clip(1 - d / 0.05, 0, 1))
    return d


def demarcation_profile(ys, zmax, zmin, frac, med=1.5, sig=0.45):
    """paint-demarcation height vs y (section centre - frac * half height), smoothed so it follows the
    body's taper without steps. The raw section table jumps wherever something sits on the body (canopy,
    turret fairing, tail housing, gear doors, wing spar), which put a hard step in the upper/lower paint
    line at that station."""
    zd = ((zmax + zmin) / 2 - frac * (zmax - zmin) / 2).astype(np.float64)
    step = float(ys[1] - ys[0])
    h = max(1, int(round(med / step / 2)))
    pad = np.pad(zd, h, mode='edge')
    zd = np.median(np.lib.stride_tricks.sliding_window_view(pad, 2 * h + 1), axis=1)
    k = np.arange(-int(3 * sig / step), int(3 * sig / step) + 1) * step
    w = np.exp(-0.5 * (k / sig) ** 2)
    w /= w.sum()
    zd = np.convolve(np.pad(zd, len(k) // 2, mode='edge'), w, mode='valid')
    return zd.astype(F32)


def compute(G, log=print):
    K = G.K
    X, Y, Z, N = G.X, G.Y, G.Z, G.N
    acc = Acc(K)
    panel_key = np.zeros(K, np.int64)
    fabric = np.zeros(K, F32)
    walk = np.zeros(K, F32)
    wear = np.full(K, 0.04, F32)
    access = np.zeros(K, F32)
    upper = np.ones(K, F32)
    antiglare = np.zeros(K, F32)
    nac_in = np.zeros(K, F32)
    exhaust = np.zeros(K, F32)

    # ------------------------------------------------------------- fuselage-like
    m = G.g('fus', 'pkg', 'blister', 'canopy')
    y, x, z = Y[m], X[m], Z[m]
    zc, hr = G.fus_center(y)
    hw = np.maximum(np.interp(y, G.fus_y, G.fus_xmax), 0.05).astype(F32)
    th = np.arctan2(x / hw, (z - zc) / np.maximum(hr, 0.05)).astype(F32)
    rbar = ((hw + hr) / 2).astype(F32)
    sub = Acc(len(y))
    is_fus = (G.group[m] == 'fus')
    # frames (rivet rows) every 0.42 m
    frames = np.arange(-9.8, 6.5, 0.42)
    d_fr, _ = nearest_station(y, frames)
    sub.add_rivets(np.ones(len(y), bool), d_fr, rbar * th, 0.032)
    # main circumferential seams
    majors = [-8.62, -7.36, -6.1, -4.32, -3.06, -1.8, -0.25, 1.24, 2.62, 3.4, 4.55, 5.25]
    d_mj, _ = nearest_station(y, majors)
    sub.add_seam(np.ones(len(y), bool), d_mj, MAJOR_D)
    # longitudinal lap joints and stringers
    longs = [-2.75, -2.0, -1.25, -0.45, 0.45, 1.25, 2.0, 2.75]
    d_lg, j_lg = wrap_dist(th, longs)
    d_lgm = d_lg * rbar
    sub.add_seam(np.ones(len(y), bool), d_lgm, SEAM_D * 0.8)
    sub.add_step(np.ones(len(y), bool), (th - np.asarray(longs, F32)[j_lg]) * rbar * np.sign(np.cos(th)), 0.0003)
    sub.add_rivets(np.ones(len(y), bool), np.abs(d_lgm - 0.012), y, 0.03)
    strs = np.arange(-math.pi, math.pi, 0.21)
    d_st, _ = wrap_dist(th, strs)
    sub.add_rivets(np.ones(len(y), bool), d_st * rbar, y, 0.055, h=STR_RIV_H)
    # canopy frame / blister: no skin detail
    nod = ~np.isin(G.group[m], ['fus', 'pkg'])
    sub.H[nod] = 0
    sub.seam[nod] = 0
    sub.rivet[nod] = 0
    # access panels
    acc_m = np.zeros(len(y), F32)
    nz, nx = N[m, 2], N[m, 0]
    top = is_fus & (nz > 0.55)
    for x0, x1 in ((-0.33, -0.03), (0.03, 0.33)):
        rect_outline(sub, top, x[top], y[top], x0, x1, 4.85, 5.72, out_access=acc_m)
    for s in (-1, 1):
        sd = is_fus & (nx * s > 0.6)
        rect_outline(sub, sd, y[sd], z[sd] - zc[sd], 4.72, 5.45, -0.18, 0.16, out_access=acc_m)      # nose ammo bay door
        rect_outline(sub, sd, y[sd], z[sd] - zc[sd], -7.6, -7.15, -0.05, 0.25, out_access=acc_m)    # tail inspection
    bot = is_fus & (nz < -0.6)
    rect_outline(sub, bot, x[bot], y[bot], -0.27, 0.27, -5.62, -4.98, out_access=acc_m)             # rear crew hatch
    rect_outline(sub, bot, x[bot], y[bot], -0.25, 0.25, 2.2, 2.75, out_access=acc_m)                # forward crew hatch
    acc.H[m] += sub.H
    acc.seam[m] = sub.seam
    acc.rivet[m] = sub.rivet
    access[m] = acc_m
    jb = bin_index(y, majors)
    panel_key[m] = 1_000_000 + jb * 100 + j_lg * (np.abs(d_lg) < 0.5).astype(np.int64) + \
        (np.floor(th / 0.9).astype(np.int64) + 10) * 1000
    # demarcation: OD down to ~1/3 of the section height, soft and slightly wavy
    wav = (fbm(G.P[m] * F32(1.0), 0.9, 2, seed=7) - 0.5) * 0.08
    zd = np.interp(y, G.fus_y, demarcation_profile(G.fus_y, G.fus_zmax, G.fus_zmin, 0.38)).astype(F32) + wav
    up_f = smoothstep(zd - 0.035, zd + 0.035, z)
    upper[m] = np.where(G.group[m] == 'canopy', 1.0, up_f)
    # anti-glare panel ahead of the windscreen
    ag = is_fus & (y > 4.3) & (nz > 0.25)
    agw = smoothstep(0.25, 0.5, nz) * smoothstep(4.3, 4.4, y) * (1 - smoothstep(0.78 * hw, 0.85 * hw, np.abs(x)))
    antiglare[m] = np.where(ag, agw, 0)
    # wear: crew-hatch edges, nose access, lower nose (crew boarding), tail cone
    wear[m] = np.maximum(wear[m], acc_m * 0.5)
    wear[m] = np.maximum(wear[m], (is_fus & (z < zc - 0.4 * hr) & (np.abs(y - 2.5) < 0.6)).astype(F32) * 0.3)
    log('[feat] fuselage', int(m.sum()))

    # ------------------------------------------------------------- nacelles, cowls, cowl flaps
    m = G.g('nac', 'cowl', 'cflap')
    y, x, z = Y[m], X[m], Z[m]
    side = np.sign(x).astype(F32)
    xc = side * 2.95
    zc, hr = G.nac_center(y)
    hr = np.maximum(hr, 0.1)
    th = np.arctan2(x - xc, z - zc).astype(F32)
    rr = np.sqrt((x - xc) ** 2 + (z - zc) ** 2)
    sub = Acc(len(y))
    grp = G.group[m]
    isn = grp == 'nac'
    isc = grp == 'cowl'
    ones = np.ones(len(y), bool)
    d_fr, _ = nearest_station(y, np.arange(-3.6, 1.6, 0.4))
    sub.add_rivets(isn, d_fr[isn], (rr * th)[isn], 0.032)
    d_mj, _ = nearest_station(y, [1.25, 0.35, -0.7, -1.75, -2.8])
    sub.add_seam(isn, d_mj[isn], MAJOR_D)
    longs = [-2.3, -1.05, 1.05, 2.3]
    d_lg, j_lg = wrap_dist(th, longs)
    sub.add_seam(isn, (d_lg * rr)[isn], SEAM_D * 0.8)
    sub.add_rivets(isn, np.abs(d_lg * rr - 0.012)[isn], y[isn], 0.03)
    d_st, _ = wrap_dist(th, np.arange(-math.pi, math.pi, 0.3))
    sub.add_rivets(isn, (d_st * rr)[isn], y[isn], 0.055, h=STR_RIV_H)
    # cowl: split lines at the sides with Dzus fasteners, mid-ring seam
    if isc.any():
        yc_mid = float(np.median(y[isc & G.inM[m]])) if (isc & G.inM[m]).any() else 2.0
        d_sp, _ = wrap_dist(th, [-math.pi / 2, math.pi / 2])
        sub.add_seam(isc, (d_sp * rr)[isc], SEAM_D)
        dz = np.sqrt((d_sp * rr - 0.018) ** 2 + periodic(y, 0.11) ** 2)
        ring = (np.exp(-((dz - 0.006) / 0.002) ** 2) * 0.0003 - np.exp(-(dz / 0.003) ** 2) * 0.0002).astype(F32)
        sub.H[isc] += ring[isc]
        sub.rivet[isc] = np.maximum(sub.rivet[isc], np.clip(1 - dz / 0.008, 0, 1)[isc])
        dy = np.abs(y - yc_mid)
        sub.add_seam(isc, dy[isc], SEAM_D)
        ymax = float(np.percentile(y[isc], 99.5))
        wear[m] = np.where(isc, np.maximum(wear[m], smoothstep(ymax - 0.12, ymax, y) * 0.8), wear[m])
    acc.H[m] += sub.H
    acc.seam[m] = np.maximum(acc.seam[m], sub.seam)
    acc.rivet[m] = np.maximum(acc.rivet[m], sub.rivet)
    panel_key[m] = 2_000_000 + (side > 0) * 500_000 + bin_index(y, [1.25, 0.35, -0.7, -1.75, -2.8]) * 100 + j_lg + isc * 50
    wav = (fbm(G.P[m], 1.1, 2, seed=8) - 0.5) * 0.06
    zd = np.interp(y, G.n_y, demarcation_profile(G.n_y, G.n_zmax, G.n_zmin, 0.28, med=1.0, sig=0.3)).astype(F32) + wav
    # up-facing nacelle surfaces are always upper colour (the aft fairing above the wing has no
    # lower half, so the section-centre rule alone would put its sides in the lower colour)
    upper[m] = np.maximum(smoothstep(zd - 0.03, zd + 0.03, z), smoothstep(0.05, 0.3, N[m, 2]) * smoothstep(0.1, 0.2, z))
    # inboard nacelle faces (anti-glare on natural-metal aircraft)
    inb = ((x - xc) * side < 0) & (y > -0.2) & (z > zc - 0.35 * hr)
    nac_in[m] = (inb * smoothstep(-0.2, 0.0, y) * smoothstep(-0.05 * 1.0, 0.05, -(x - xc) * side)).astype(F32)
    # exhaust streaks from the stub outlets, running aft
    outs = []
    for s_, pts in G.exhaust.items():
        for p in pts:
            if not any(abs(p[0] - q[0]) < 0.08 and abs(p[2] - q[2]) < 0.08 for q in outs):
                outs.append(p)
    P = G.P[m]
    streak = fbm(P * np.array([1.0, 0.15, 1.0], F32), 9.0, 3, seed=21)
    ex = np.zeros(len(y), F32)
    for ox, oy, oz in outs:
        s_ = 1 if ox > 0 else -1
        if np.sign(x[0]) == 0:
            pass
        sel = (np.sign(x) == s_)
        along = oy - y
        tho = math.atan2(ox - s_ * 2.95, oz - 0.0)
        lat = np.abs(((th - tho) + math.pi) % TAU - math.pi) * rr
        wdt = 0.045 + 0.13 * np.clip(along, 0, None)
        v = np.exp(-np.clip(along, 0, None) / 2.6) * np.exp(-(lat / wdt) ** 2) * smoothstep(-0.03, 0.06, along)
        ex = np.maximum(ex, np.where(sel, v, 0))
    exhaust[m] = ex * (0.55 + 0.45 * streak)
    log('[feat] nacelles', int(m.sum()), 'exhaust outlets', len(outs))

    # ------------------------------------------------------------- wings, flaps, ailerons
    m = G.g('wing', 'flap', 'ail')
    y, x, z = Y[m], X[m], Z[m]
    ax = np.abs(x)
    c, ch = G.wing_chord(ax, y)
    cm = c * ch
    grp = G.group[m]
    isw, isf, isa = grp == 'wing', grp == 'flap', grp == 'ail'
    nz = N[m, 2]
    sub = Acc(len(y))
    ribs = np.arange(0.75, 10.2, 0.46)
    d_rb, _ = nearest_station(ax, ribs)
    sub.add_rivets(isw, d_rb[isw], cm[isw], 0.035)
    joints = [2.95, 6.15]
    d_j, _ = nearest_station(ax, joints)
    sub.add_seam(isw, d_j[isw], MAJOR_D)
    d_j2, _ = nearest_station(ax, [1.62, 4.45, 7.9])
    sub.add_seam(isw, d_j2[isw], SEAM_D * 0.8)
    spars = [0.12, 0.22, 0.62]
    for k, cs in enumerate(spars):
        dc = np.abs(c - cs) * ch
        if k == 0:
            sub.add_seam(isw, dc[isw], SEAM_D * 0.8)
        sub.add_rivets(isw, np.abs(dc - (0.0 if k else 0.012))[isw], ax[isw], 0.03)
    strs = np.arange(0.28, 0.6, 0.065)
    d_s, _ = nearest_station(c, strs)
    sub.add_rivets(isw, (d_s * ch)[isw], ax[isw], 0.06, h=STR_RIV_H)
    # flaps: metal ribs
    d_fr, _ = nearest_station(ax, np.arange(0.6, 6.2, 0.25))
    sub.add_rivets(isf, d_fr[isf], cm[isf], 0.035)
    # ailerons: doped fabric over ribs - rib tapes and pillowing
    pitch = 0.15
    fr = ((ax - 6.2) / pitch) % 1.0
    d_r = np.minimum(fr, 1 - fr) * pitch
    tape = 0.00035 * (1 - smoothstep(0.009, 0.014, d_r))
    pillow = -0.0009 * np.sin(np.pi * fr) ** 1.5
    sub.H[isa] += (tape + pillow)[isa]
    sub.seam[isa] = np.maximum(sub.seam[isa], (0.12 * (1 - smoothstep(0.012, 0.016, d_r)))[isa])
    fabric[m] = isa.astype(F32)
    # access panels underneath, fuel fillers on top
    acc_m = np.zeros(len(y), F32)
    under = isw & (nz < -0.3)
    for st in (1.85, 4.15, 5.2, 7.0, 8.55):
        rect_outline(sub, under, ax[under], c[under] * ch[under], st - 0.17, st + 0.17,
                     float(np.interp(st, G.w_x, G.w_le - G.w_te)) * 0.30,
                     float(np.interp(st, G.w_x, G.w_le - G.w_te)) * 0.44, out_access=acc_m)
    topw = isw & (nz > 0.3)
    for st, cc in ((1.75, 0.38), (4.6, 0.36), (5.6, 0.36)):
        chs = float(np.interp(st, G.w_x, G.w_le - G.w_te))
        dd = np.sqrt((ax - st) ** 2 + (cm - cc * chs) ** 2)
        g1 = groove(np.abs(dd - 0.075), 0.004, SEAM_D)
        g2 = groove(np.abs(dd - 0.045), 0.003, SEAM_D * 0.6)
        sub.H[topw] += (g1 + g2)[topw]
        sub.seam[topw] = np.maximum(sub.seam[topw], (-g1 / SEAM_D)[topw])
        acc_m[topw] = np.maximum(acc_m[topw], np.clip(1 - dd / 0.12, 0, 1)[topw])
    acc.H[m] += sub.H
    acc.seam[m] = np.maximum(acc.seam[m], sub.seam)
    acc.rivet[m] = np.maximum(acc.rivet[m], sub.rivet)
    access[m] = np.maximum(access[m], acc_m)
    panel_key[m] = 3_000_000 + (x > 0) * 500_000 + (nz > 0) * 250_000 + \
        bin_index(ax, [1.62, 2.95, 4.45, 6.15, 7.9]) * 100 + bin_index(c, [0.12, 0.62]) * 10 + isf * 7 + isa * 8
    upper[m] = smoothstep(-0.38, -0.08, nz)
    # walkway on the inner wing top, between fuselage and nacelle
    wk = isw & (nz > 0.2) & (ax > 0.7) & (ax < 1.95) & (c > 0.2) & (c < 0.78)
    walk[m] = (wk * smoothstep(0.7, 0.8, ax) * (1 - smoothstep(1.85, 1.95, ax)) *
               smoothstep(0.2, 0.25, c) * (1 - smoothstep(0.72, 0.78, c))).astype(F32)
    le = 1 - smoothstep(0.0, 0.06, c)
    wear[m] = np.maximum(wear[m], np.maximum(le * 0.6, walk[m] * 0.22))
    wear[m] = np.maximum(wear[m], acc_m * 0.5)
    wear[m] = np.maximum(wear[m], (isf & (nz > 0.2)).astype(F32) * 0.25)
    # exhaust streaks spill over the wing near the nacelles
    P = G.P[m]
    streak = fbm(P * np.array([1.0, 0.15, 1.0], F32), 9.0, 3, seed=22)
    ex = np.zeros(len(y), F32)
    for ox, oy, oz in outs:
        along = oy - y
        lat = np.abs(x - ox)
        face = (nz > 0) if oz > 0.1 else (nz < 0)
        wdt = 0.04 + 0.11 * np.clip(along, 0, None)
        v = np.exp(-np.clip(along, 0, None) / 1.6) * np.exp(-(lat / wdt) ** 2) * smoothstep(0.0, 0.1, along)
        ex = np.maximum(ex, np.where(face & (np.abs(z - oz) < 0.6), v, 0))
    exhaust[m] = ex * (0.5 + 0.5 * streak) * 0.8
    log('[feat] wings', int(m.sum()))

    # ------------------------------------------------------------- tailplane
    m = G.g('stab', 'elev')
    y, x = Y[m], X[m]
    ax = np.abs(x)
    c, ch = G.stab_chord(ax, y)
    cm = c * ch
    grp = G.group[m]
    iss, ise = grp == 'stab', grp == 'elev'
    nz = N[m, 2]
    sub = Acc(len(y))
    d_rb, _ = nearest_station(ax, np.arange(0.5, 3.6, 0.38))
    sub.add_rivets(iss, d_rb[iss], cm[iss], 0.032)
    for cs in (0.15, 0.55):
        dc = np.abs(c - cs) * ch
        sub.add_rivets(iss, dc[iss], ax[iss], 0.03)
    sub.add_seam(iss, (np.abs(c - 0.15) * ch)[iss], SEAM_D * 0.7)
    pitch = 0.14
    fr = (ax / pitch) % 1.0
    d_r = np.minimum(fr, 1 - fr) * pitch
    sub.H[ise] += (0.00035 * (1 - smoothstep(0.009, 0.014, d_r)) - 0.0009 * np.sin(np.pi * fr) ** 1.5)[ise]
    sub.seam[ise] = np.maximum(sub.seam[ise], (0.12 * (1 - smoothstep(0.012, 0.016, d_r)))[ise])
    fabric[m] = ise.astype(F32)
    acc.H[m] += sub.H
    acc.seam[m] = np.maximum(acc.seam[m], sub.seam)
    acc.rivet[m] = np.maximum(acc.rivet[m], sub.rivet)
    panel_key[m] = 4_000_000 + (x > 0) * 500_000 + (nz > 0) * 250_000 + ise * 9 + bin_index(c, [0.15]) * 10
    upper[m] = smoothstep(-0.38, -0.08, nz)
    wear[m] = np.maximum(wear[m], (1 - smoothstep(0.0, 0.06, c)) * 0.8)

    m = G.g('fin', 'rud')
    y, z = Y[m], Z[m]
    c, ch = G.fin_chord(z, y)
    cm = c * ch
    grp = G.group[m]
    isf, isr = grp == 'fin', grp == 'rud'
    sub = Acc(len(y))
    d_rb, _ = nearest_station(z, np.arange(0.25, 3.4, 0.36))
    sub.add_rivets(isf, d_rb[isf], cm[isf], 0.032)
    for cs in (0.15, 0.55):
        sub.add_rivets(isf, (np.abs(c - cs) * ch)[isf], z[isf], 0.03)
    sub.add_seam(isf, (np.abs(c - 0.15) * ch)[isf], SEAM_D * 0.7)
    pitch = 0.14
    fr = (z / pitch) % 1.0
    d_r = np.minimum(fr, 1 - fr) * pitch
    sub.H[isr] += (0.00035 * (1 - smoothstep(0.009, 0.014, d_r)) - 0.0009 * np.sin(np.pi * fr) ** 1.5)[isr]
    sub.seam[isr] = np.maximum(sub.seam[isr], (0.12 * (1 - smoothstep(0.012, 0.016, d_r)))[isr])
    fabric[m] = isr.astype(F32)
    acc.H[m] += sub.H
    acc.seam[m] = np.maximum(acc.seam[m], sub.seam)
    acc.rivet[m] = np.maximum(acc.rivet[m], sub.rivet)
    panel_key[m] = 5_000_000 + (X[m] > 0) * 500_000 + (N[m, 0] > 0) * 250_000 + isr * 9 + bin_index(c, [0.15]) * 10
    upper[m] = 1.0
    wear[m] = np.maximum(wear[m], (1 - smoothstep(0.0, 0.06, c)) * 0.8)
    log('[feat] tail', int(m.sum()))

    # ------------------------------------------------------------- shared weathering fields
    other = G.group == ''
    panel_key[other] = 9_000_000 + G.oid[other]
    panel = hash1(panel_key, 3)
    P = G.P
    log('[feat] noise ...')
    fade = fbm(P, 0.45, 3, seed=31)
    hf = fbm(P, 55.0, 3, seed=41)
    try:
        scr = tri_sample(load_tile('scratch_chips', 512), P, N, 0.9, seed=1)
        blot = tri_sample(load_tile('grime_blotch', 256), P, N, 2.2, seed=2)
    except Exception as e:     # fal tiles missing -> procedural fallback
        log('[feat] fal tiles unavailable, procedural fallback', e)
        scr = np.zeros(K, F32)
        blot = 1 - fbm(P, 1.5, 3, seed=55)
    # chipping: wear-weighted threshold of high-frequency noise, plus scratches in worn areas
    thr = 1.0 - 0.34 * wear
    chip = smoothstep(thr - 0.015, thr + 0.015, hf + 0.18 * wear)
    chip = np.maximum(chip, smoothstep(0.55, 0.85, scr) * np.clip(wear * 1.6, 0, 1) * 0.9)
    chip *= (1 - fabric * 0.7)
    grime = np.clip((1 - blot) * 1.3, 0, 1) * 0.6 + 0.4 * fbm(P, 3.0, 3, seed=61)
    grime = np.clip(grime + 0.25 * (1 - upper) * (G.g('fus', 'nac')), 0, 1)
    # bottom of the fuselage aft of the bomb bay gets oily
    belly = G.g('fus') & (N[:, 2] < -0.5) & (Y < 0.5)
    grime = np.where(belly, np.clip(grime + 0.25 * smoothstep(0.5, -2.0, Y), 0, 1), grime)
    return dict(H=acc.H, seam=np.clip(acc.seam, 0, 1), rivet=np.clip(acc.rivet, 0, 1), panel=panel,
                fabric=fabric, walk=walk, wear=np.clip(wear, 0, 1), chip=np.clip(chip, 0, 1),
                upper=np.clip(upper, 0, 1), antiglare=antiglare, nac_inboard=nac_in,
                exhaust=np.clip(exhaust, 0, 1), grime=grime.astype(F32), fade=fade, access=access)
