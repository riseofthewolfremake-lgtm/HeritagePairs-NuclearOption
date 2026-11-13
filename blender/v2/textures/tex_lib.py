"""Shared helpers for the B-25H v2 texture build (run inside Blender's Python: bpy + numpy).

Everything on the livery atlas is evaluated per texel from the baked world position / normal /
object id (bake_maps.py), so features are continuous across atlas seams by construction.
Arrays are kept "compressed": only texels inside the extended island mask, length K.
Image arrays use Blender's row order (row 0 = v 0 = bottom); PNGs are written the right way up.
"""
import bpy, os, json, math
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
OUT = os.path.join(ROOT, 'assets', 'textures_v2')
FAL = os.path.join(OUT, 'fal_raw')
F32 = np.float32


# ------------------------------------------------------------------ image io
def load_image(path, nonc=True):
    im = bpy.data.images.load(path, check_existing=False)
    if nonc:
        im.colorspace_settings.name = 'Non-Color'
    w, h = im.size
    a = np.empty(w * h * 4, F32)
    im.pixels.foreach_get(a)
    bpy.data.images.remove(im)
    return a.reshape(h, w, 4)


def save_png(arr, path, alpha=None):
    """arr: HxW (grey) or HxWx3/4 floats in 0-1, display-encoded values written byte-for-byte."""
    arr = np.asarray(arr, F32)
    h, w = arr.shape[:2]
    if arr.ndim == 2:
        arr = np.dstack([arr, arr, arr])
    if arr.shape[2] == 3:
        a = np.ones((h, w), F32) if alpha is None else alpha
        arr = np.dstack([arr, a])
    arr = np.clip(arr, 0, 1)
    im = bpy.data.images.new(os.path.basename(path), w, h, alpha=True)
    im.colorspace_settings.name = 'Non-Color'
    im.pixels.foreach_set(arr.ravel())
    im.filepath_raw = path
    im.file_format = 'PNG'
    im.save()
    bpy.data.images.remove(im)
    print('[tex] wrote', os.path.relpath(path, ROOT), f'{w}x{h}')


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


# ------------------------------------------------------------------ noise (seamless: evaluated in 3D)
def _hash(ix, iy, iz, seed):
    h = (ix * 73856093) ^ (iy * 19349663) ^ (iz * 83492791) ^ (seed * 2654435761 + 1013904223)
    h &= 0xFFFFFFFF
    h ^= h >> 15
    h = (h * 2246822519) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * 3266489917) & 0xFFFFFFFF
    h ^= h >> 16
    return (h & 0xFFFFFF).astype(F32) * (1.0 / 0xFFFFFF)


def vnoise(P, freq, seed=0, chunk=4_000_000):
    """value noise in [0,1], P (K,3) metres; freq in cycles per metre (scalar or 3-vector)."""
    out = np.empty(len(P), F32)
    fr = np.asarray(freq, F32)
    for s in range(0, len(P), chunk):
        q = P[s:s + chunk] * fr
        i = np.floor(q)
        f = (q - i).astype(F32)
        i = i.astype(np.int64)
        u = f * f * (3 - 2 * f)
        ix, iy, iz = i[:, 0], i[:, 1], i[:, 2]
        acc = np.zeros(len(q), F32)
        for dx in (0, 1):
            wx = u[:, 0] if dx else 1 - u[:, 0]
            for dy in (0, 1):
                wy = u[:, 1] if dy else 1 - u[:, 1]
                for dz in (0, 1):
                    wz = u[:, 2] if dz else 1 - u[:, 2]
                    acc += wx * wy * wz * _hash(ix + dx, iy + dy, iz + dz, seed)
        out[s:s + chunk] = acc
    return out


def fbm(P, freq, octaves=4, seed=0, gain=0.5, lac=2.03):
    tot = np.zeros(len(P), F32)
    amp, norm = 1.0, 0.0
    fr = np.asarray(freq, F32)
    for o in range(octaves):
        tot += amp * vnoise(P, fr, seed + 101 * o)
        norm += amp
        amp *= gain
        fr = fr * lac
    return tot / norm


def hash1(i, seed=0):
    i = np.asarray(i, np.int64)
    return _hash(i, i * 7 + 3, i * 13 + 5, seed)


# ------------------------------------------------------------------ 1-D feature helpers
def nearest_station(s, stations):
    """distance from s to the nearest value in sorted `stations`, and its index."""
    st = np.asarray(sorted(stations), F32)
    j = np.clip(np.searchsorted(st, s), 1, len(st) - 1)
    d0 = np.abs(s - st[j - 1])
    d1 = np.abs(st[j] - s)
    pick = d1 < d0
    return np.where(pick, d1, d0).astype(F32), np.where(pick, j, j - 1)


def periodic(s, spacing, offset=0.0):
    t = (s - offset) / spacing
    return (np.abs(t - np.round(t)) * spacing).astype(F32)


def bin_index(s, stations):
    return np.searchsorted(np.asarray(sorted(stations), F32), s)


def groove(d, half_w, depth):
    """V/gaussian groove profile (negative height)."""
    return (-depth * np.exp(-(d / half_w) ** 2)).astype(F32)


def dome(d, r, h):
    t = np.clip(1 - (d / r) ** 2, 0, 1)
    return (h * np.sqrt(t)).astype(F32)


# ------------------------------------------------------------------ geometry
GROUPS = {
    'fus': ('fus_', 'bomb_door_', 'gear_door_nose_', 'hatch_entry_'),
    'canopy': ('canopy_frame', 'hatch_cockpit_top', 'turret_dorsal'),
    'pkg': ('package_guns_',),
    'nac': ('nacelle_', 'gear_door_main_'),
    'cowl': ('engine_',),
    'cflap': ('cowl_flap_',),
    'wing': ('wing_inner_', 'wing_outer_', 'wing_tip_'),
    'flap': ('flap_',),
    'ail': ('aileron_',),
    'stab': ('stab_',),
    'elev': ('elevator_',),
    'fin': ('fin_',),
    'rud': ('rudder_',),
    'blister': ('waist_blister_', 'hatch_waist_'),
    'pylon': ('pylon_',),
}


class Geo:
    def __init__(self, cache):
        self.cache = cache
        pos = load_image(os.path.join(cache, 'pos.exr'))
        self.res = pos.shape[0]
        R = self.res
        self.maskM = pos[..., 3] > 0.5           # true paint texel
        # nearest-texel dilation of every baked map past the island edges (margin for filtering/mips)
        margin = max(6, R // 170)
        src = dilate_index(self.maskM, margin)
        self.maskX = src >= 0                    # paint texel incl. margin
        self.idx = np.flatnonzero(self.maskX.ravel())
        sidx = src.ravel()[self.idx]
        K = len(self.idx)
        self.K = K
        self.P = pos.reshape(-1, 4)[sidx, :3].copy()
        del pos
        nrm = load_image(os.path.join(cache, 'nrm.exr'))
        N = nrm.reshape(-1, 4)[sidx, :3].copy()
        N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-6)
        self.N = N.astype(F32)
        del nrm
        oid = load_image(os.path.join(cache, 'oid.exr'))
        self.oid = np.rint(oid.reshape(-1, 4)[sidx, 0]).astype(np.int32)
        del oid
        ao = load_image(os.path.join(cache, 'ao.exr'))
        aof = np.ones(R * R, F32)
        aof[self.idx] = ao.reshape(-1, 4)[sidx, 0]
        self.ao_full = aof.reshape(R, R)
        del ao
        self.inM = self.maskM.ravel()[self.idx]
        with open(os.path.join(cache, 'objects.json')) as f:
            self.objects = {int(k): v for k, v in json.load(f).items()}
        with open(os.path.join(cache, 'exhaust.json')) as f:
            self.exhaust = json.load(f)
        names = {k: v['name'] for k, v in self.objects.items()}
        self.names = names
        self.group = np.full(K, '', dtype='<U8')
        gid = {}
        for k, nm in names.items():
            for g, pre in GROUPS.items():
                if nm.startswith(pre):
                    gid[k] = g
        lut = np.array([gid.get(i, '') for i in range(max(names) + 1)], dtype='<U8')
        self.group = lut[np.clip(self.oid, 0, len(lut) - 1)]
        self.X, self.Y, self.Z = self.P[:, 0], self.P[:, 1], self.P[:, 2]
        self.side = np.where(self.X < 0, -1, 1).astype(np.int8)
        # texel size in metres from the build stats in the .blend (metres per uv unit)
        self.m_per_uv = 19.297
        self.ts = self.m_per_uv / R
        self._tables()

    # masks by group name
    def g(self, *names):
        m = np.zeros(self.K, bool)
        for n in names:
            m |= self.group == n
        return m

    # ---------------------------------------------------------- data-driven section / chord tables
    @staticmethod
    def _table(key, val, lo, hi, step, fn):
        nb = int(round((hi - lo) / step)) + 1
        b = np.clip(((key - lo) / step).astype(np.int64), 0, nb - 1)
        out = np.full(nb, np.nan, F32)
        if fn == 'max':
            tmp = np.full(nb, -1e9, F32)
            np.maximum.at(tmp, b, val)
            out = np.where(tmp > -1e8, tmp, np.nan)
        else:
            tmp = np.full(nb, 1e9, F32)
            np.minimum.at(tmp, b, val)
            out = np.where(tmp < 1e8, tmp, np.nan)
        xs = lo + step * np.arange(nb)
        ok = ~np.isnan(out)
        out = np.interp(xs, xs[ok], out[ok]).astype(F32)
        return xs.astype(F32), out

    def _tables(self):
        X, Y, Z = self.X, self.Y, self.Z
        inM = self.inM
        # fuselage section vs y
        m = self.g('fus') & inM & (np.abs(X) < 1.3)
        self.fus_y, self.fus_zmax = self._table(Y[m], Z[m], -10.0, 6.6, 0.02, 'max')
        _, self.fus_zmin = self._table(Y[m], Z[m], -10.0, 6.6, 0.02, 'min')
        _, self.fus_xmax = self._table(Y[m], np.abs(X[m]), -10.0, 6.6, 0.02, 'max')
        # wing chord vs |x| (wing + flaps + ailerons, both sides pooled)
        m = self.g('wing', 'flap', 'ail') & inM
        self.w_x, self.w_le = self._table(np.abs(X[m]), Y[m], 0.0, 10.4, 0.02, 'max')
        _, self.w_te = self._table(np.abs(X[m]), Y[m], 0.0, 10.4, 0.02, 'min')
        m = self.g('stab', 'elev') & inM
        self.s_x, self.s_le = self._table(np.abs(X[m]), Y[m], 0.0, 3.7, 0.02, 'max')
        _, self.s_te = self._table(np.abs(X[m]), Y[m], 0.0, 3.7, 0.02, 'min')
        m = self.g('fin', 'rud') & inM
        self.f_z, self.f_le = self._table(Z[m], Y[m], 0.0, 3.6, 0.02, 'max')
        _, self.f_te = self._table(Z[m], Y[m], 0.0, 3.6, 0.02, 'min')
        m = self.g('nac', 'cowl') & inM & (np.abs(np.abs(X) - 2.95) < 0.9)
        self.n_y, self.n_zmax = self._table(Y[m], Z[m], -4.0, 3.0, 0.02, 'max')
        _, self.n_zmin = self._table(Y[m], Z[m], -4.0, 3.0, 0.02, 'min')

    def fus_center(self, y):
        zmax = np.interp(y, self.fus_y, self.fus_zmax)
        zmin = np.interp(y, self.fus_y, self.fus_zmin)
        return ((zmax + zmin) / 2).astype(F32), ((zmax - zmin) / 2).astype(F32)

    def wing_chord(self, ax, y):
        le = np.interp(ax, self.w_x, self.w_le)
        te = np.interp(ax, self.w_x, self.w_te)
        ch = np.maximum(le - te, 0.05)
        return ((le - y) / ch).astype(F32), ch.astype(F32)

    def stab_chord(self, ax, y):
        le = np.interp(ax, self.s_x, self.s_le)
        te = np.interp(ax, self.s_x, self.s_te)
        ch = np.maximum(le - te, 0.05)
        return ((le - y) / ch).astype(F32), ch.astype(F32)

    def fin_chord(self, z, y):
        le = np.interp(z, self.f_z, self.f_le)
        te = np.interp(z, self.f_z, self.f_te)
        ch = np.maximum(le - te, 0.05)
        return ((le - y) / ch).astype(F32), ch.astype(F32)

    def nac_center(self, y):
        zmax = np.interp(y, self.n_y, self.n_zmax)
        zmin = np.interp(y, self.n_y, self.n_zmin)
        return ((zmax + zmin) / 2).astype(F32), ((zmax - zmin) / 2).astype(F32)

    # ---------------------------------------------------------- scatter / gather
    def full(self, v, fill=0.0):
        """compressed (K,) or (K,C) -> res x res (x C) image array (row 0 = bottom)."""
        R = self.res
        v = np.asarray(v, F32)
        if v.ndim == 1:
            out = np.full(R * R, fill, F32)
            out[self.idx] = v
            return out.reshape(R, R)
        out = np.full((R * R, v.shape[1]), fill, F32)
        out[self.idx] = v
        return out.reshape(R, R, v.shape[1])

    def gather(self, img):
        img = np.asarray(img)
        if img.ndim == 2:
            return img.ravel()[self.idx]
        return img.reshape(-1, img.shape[2])[self.idx]


HINGE_GAP_COL = np.array((0.045, 0.045, 0.048), np.float32)


def hinge_gap(G):
    """seam fix (2026-10-31): coverage (K) of the forward-facing nose faces of the control surfaces (elevators,
    ailerons, flaps, rudders). They sit 4 mm behind the fixed surface's hinge wall; seen through the hinge gap they took
    the upper/lower blend colour (light underside colours) at grazing light and read as a light seam line along every
    hinge in all liveries. Painted as a dark shadowed gap (base colour, AO, smoothness)."""
    g = G.g('elev', 'ail', 'flap', 'rud')
    return np.where(g, smoothstep(0.45, 0.75, G.N[:, 1]), 0).astype(np.float32)


def dilate_index(mask, iters):
    """flat index of the nearest masked texel (approx., 8-neighbour propagation) or -1."""
    h, w = mask.shape
    idx = np.where(mask.ravel(), np.arange(h * w, dtype=np.int64), -1).reshape(h, w)
    for _ in range(iters):
        empty = idx < 0
        if not empty.any():
            break
        new = idx.copy()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            s = np.roll(idx, (dy, dx), (0, 1))
            take = (new < 0) & (s >= 0)
            new[take] = s[take]
        idx = new
    return idx


def fill_outside(img, mask, iters=48):
    """push island colours outward (simple dilation by neighbour average) so mips/filtering don't
    pull in background; leaves a neutral mean beyond."""
    img = img.copy()
    m = mask.copy()
    for _ in range(iters):
        acc = np.zeros_like(img)
        cnt = np.zeros(m.shape, F32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            sm = np.roll(m, (dy, dx), (0, 1))
            si = np.roll(img, (dy, dx), (0, 1))
            if img.ndim == 3:
                acc += si * sm[..., None]
            else:
                acc += si * sm
            cnt += sm
        grow = (~m) & (cnt > 0)
        if not grow.any():
            break
        if img.ndim == 3:
            img[grow] = acc[grow] / cnt[grow][:, None]
        else:
            img[grow] = acc[grow] / cnt[grow]
        m = m | grow
    if (~m).any():
        mean = img[mask].mean(axis=0)
        img[~m] = mean
    return img


def blur(img, r=1):
    """box blur radius r (separable, wraps at borders: fine for padded atlases)."""
    out = img.astype(F32)
    for ax in (0, 1):
        acc = np.zeros_like(out)
        for d in range(-r, r + 1):
            acc += np.roll(out, d, ax)
        out = acc / (2 * r + 1)
    return out


def normal_from_height(H, ts, strength=1.0):
    """H: res x res height in metres (row 0 = v 0). Tangent-space normal, OpenGL (+Y = +v)."""
    dhdu = (np.roll(H, -1, 1) - np.roll(H, 1, 1)) / (2 * ts)
    dhdv = (np.roll(H, -1, 0) - np.roll(H, 1, 0)) / (2 * ts)
    nx, ny = -dhdu * strength, -dhdv * strength
    nz = np.ones_like(H)
    l = np.sqrt(nx * nx + ny * ny + nz * nz)
    return np.dstack([nx / l, ny / l, nz / l]).astype(F32)


def encode_normal(n):
    return np.clip(n * 0.5 + 0.5, 0, 1)


# ------------------------------------------------------------------ triplanar tile sampling (fal tiles)
def load_tile(name, size=256, grey=True):
    a = load_image(os.path.join(FAL, name + '.png'))
    h = a.shape[0]
    f = h // size
    a = a[:size * f, :size * f, :3].reshape(size, f, size, f, 3).mean(axis=(1, 3))
    if grey:
        a = a.mean(-1)
    return a.astype(F32)


def tri_sample(tile, P, N, span, sharp=4.0, seed=0):
    """triplanar sample of a seamless tile; span = metres covered by one tile."""
    T = tile.shape[0]
    w = np.abs(N) ** sharp
    w /= w.sum(axis=1, keepdims=True)
    off = [(0.37 * seed) % 1, (0.61 * seed) % 1]
    out = 0
    for ax, (a, b) in enumerate(((1, 2), (0, 2), (0, 1))):
        u = (P[:, a] / span + off[0]) % 1.0 * T
        v = (P[:, b] / span + off[1]) % 1.0 * T
        i0 = np.floor(u).astype(np.int64) % T
        j0 = np.floor(v).astype(np.int64) % T
        fu = (u - np.floor(u)).astype(F32)
        fv = (v - np.floor(v)).astype(F32)
        i1, j1 = (i0 + 1) % T, (j0 + 1) % T
        if tile.ndim == 2:
            s = (tile[j0, i0] * (1 - fu) * (1 - fv) + tile[j0, i1] * fu * (1 - fv) +
                 tile[j1, i0] * (1 - fu) * fv + tile[j1, i1] * fu * fv)
            out = out + s * w[:, ax]
        else:
            s = (tile[j0, i0] * ((1 - fu) * (1 - fv))[:, None] + tile[j0, i1] * (fu * (1 - fv))[:, None] +
                 tile[j1, i0] * ((1 - fu) * fv)[:, None] + tile[j1, i1] * (fu * fv)[:, None])
            out = out + s * w[:, ax:ax + 1]
    return out.astype(F32)


# ------------------------------------------------------------------ stroke font (original, 4x6 grid)
_G = {
    'A': ['0,0 0,4 2,6 4,4 4,0', '0,3 4,3'], 'B': ['0,0 0,6 3,6 4,5 4,4 3,3 0,3', '3,3 4,2 4,1 3,0 0,0'],
    'C': ['4,1 3,0 1,0 0,1 0,5 1,6 3,6 4,5'], 'D': ['0,0 0,6 2,6 4,4 4,2 2,0 0,0'],
    'E': ['4,0 0,0 0,6 4,6', '0,3 3,3'], 'F': ['0,0 0,6 4,6', '0,3 3,3'],
    'G': ['4,5 3,6 1,6 0,5 0,1 1,0 3,0 4,1 4,3 2,3'], 'H': ['0,0 0,6', '4,0 4,6', '0,3 4,3'],
    'I': ['1,0 3,0', '2,0 2,6', '1,6 3,6'], 'J': ['0,1 1,0 3,0 4,1 4,6'], 'K': ['0,0 0,6', '4,6 0,2', '1,3 4,0'],
    'L': ['0,6 0,0 4,0'], 'M': ['0,0 0,6 2,3 4,6 4,0'], 'N': ['0,0 0,6 4,0 4,6'],
    'O': ['1,0 3,0 4,1 4,5 3,6 1,6 0,5 0,1 1,0'], 'P': ['0,0 0,6 3,6 4,5 4,4 3,3 0,3'],
    'Q': ['1,0 3,0 4,1 4,5 3,6 1,6 0,5 0,1 1,0', '2,2 4,0'], 'R': ['0,0 0,6 3,6 4,5 4,4 3,3 0,3', '2,3 4,0'],
    'S': ['0,1 1,0 3,0 4,1 4,2 3,3 1,3 0,4 0,5 1,6 3,6 4,5'], 'T': ['0,6 4,6', '2,6 2,0'],
    'U': ['0,6 0,1 1,0 3,0 4,1 4,6'], 'V': ['0,6 2,0 4,6'], 'W': ['0,6 1,0 2,3 3,0 4,6'],
    'X': ['0,0 4,6', '0,6 4,0'], 'Y': ['0,6 2,3 4,6', '2,3 2,0'], 'Z': ['0,6 4,6 0,0 4,0'],
    '0': ['1,0 3,0 4,1 4,5 3,6 1,6 0,5 0,1 1,0'], '1': ['1,5 2,6 2,0', '1,0 3,0'],
    '2': ['0,5 1,6 3,6 4,5 4,4 0,0 4,0'], '3': ['0,5 1,6 3,6 4,5 4,4 3,3 4,2 4,1 3,0 1,0 0,1', '1,3 3,3'],
    '4': ['3,0 3,6 0,2 4,2'], '5': ['4,6 0,6 0,3 3,3 4,2 4,1 3,0 0,0'],
    '6': ['4,5 3,6 1,6 0,5 0,1 1,0 3,0 4,1 4,2 3,3 0,3'], '7': ['0,6 4,6 1,0'],
    '8': ['1,3 0,4 0,5 1,6 3,6 4,5 4,4 3,3 1,3 0,2 0,1 1,0 3,0 4,1 4,2 3,3'],
    '9': ['0,1 1,0 3,0 4,1 4,5 3,6 1,6 0,5 0,4 1,3 4,3'],
    '-': ['1,3 3,3'], '.': ['2,0 2,0.3'], '/': ['0,0 4,6'], ' ': [], ':': ['2,1 2,1.3', '2,4 2,4.3'],
}


def glyph_segments(text, height, advance=5.6):
    """list of (x0,y0,x1,y1) segments in metres; origin = left baseline; returns (segs, width)."""
    u = height / 6.0
    segs = []
    x = 0.0
    for ch in text.upper():
        for stroke in _G.get(ch, []):
            pts = [tuple(float(c) for c in p.split(',')) for p in stroke.split()]
            for a, b in zip(pts[:-1], pts[1:]):
                segs.append(((x + a[0]) * u, a[1] * u, (x + b[0]) * u, b[1] * u))
        x += advance
    return segs, (x - (advance - 4)) * u


def seg_dist(px, py, segs):
    d = np.full(px.shape, 1e9, F32)
    for x0, y0, x1, y1 in segs:
        dx, dy = x1 - x0, y1 - y0
        L2 = dx * dx + dy * dy
        if L2 < 1e-12:
            t = 0.0
        else:
            t = np.clip(((px - x0) * dx + (py - y0) * dy) / L2, 0, 1)
        ex = px - (x0 + t * dx)
        ey = py - (y0 + t * dy)
        d = np.minimum(d, np.sqrt(ex * ex + ey * ey))
    return d


def text_mask(pu, pv, lines, height, stroke, line_gap=1.6, align='center', aa=None):
    """coverage (0-1) of multi-line text; pu/pv local metres (pu = reading direction, pv = up);
    block centred on the origin."""
    cov = np.zeros(pu.shape, F32)
    n = len(lines)
    aa = aa or stroke * 0.5
    for i, ln in enumerate(lines):
        segs, w = glyph_segments(ln, height)
        oy = (n - 1) / 2 * height * line_gap - i * height * line_gap - height / 2
        ox = -w / 2 if align == 'center' else 0.0
        sel = (pv > oy - height) & (pv < oy + 2 * height) & (pu > ox - height) & (pu < ox + w + height)
        if not sel.any():
            continue
        d = seg_dist(pu[sel] - ox, pv[sel] - oy, segs)
        cov[sel] = np.maximum(cov[sel], 1 - smoothstep(stroke / 2 - aa, stroke / 2 + aa, d))
    return cov


# ------------------------------------------------------------------ national insignia (SDF, original drawing)
def sd_star5(px, py, r, rf=0.382):
    """signed distance to a 5-point star (one point toward +py), outer radius r (after I. Quilez)."""
    k1x, k1y = 0.809016994375, -0.587785252292
    k2x, k2y = -k1x, k1y
    px = np.abs(px)
    d = np.maximum(k1x * px + k1y * py, 0) * 2
    px, py = px - d * k1x, py - d * k1y
    d = np.maximum(k2x * px + k2y * py, 0) * 2
    px, py = px - d * k2x, py - d * k2y
    px = np.abs(px)
    py = py - r
    bax, bay = rf * -k1y, rf * k1x - 1.0
    h = np.clip((px * bax + py * bay) / (bax * bax + bay * bay), 0, r)
    dx, dy = px - bax * h, py - bay * h
    return np.sqrt(dx * dx + dy * dy) * np.sign(py * bax - px * bay)


def sd_box(px, py, cx, cy, hx, hy):
    qx = np.abs(px - cx) - hx
    qy = np.abs(py - cy) - hy
    return np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qy, 0) ** 2) + np.minimum(np.maximum(qx, qy), 0)


def star_and_bar(pu, pv, R, aa):
    """returns (blue, white) coverages for the 1943-pattern star-and-bar with blue surround.
    pu along the bars, pv toward the star's top point; R = circle radius."""
    circ = np.sqrt(pu * pu + pv * pv) - R
    bar_top = R * math.sin(math.radians(18))        # in line with the star's horizontal arms
    bar_h = 0.5 * R
    bars = sd_box(pu, pv, 0.0, bar_top - bar_h / 2, 2.0 * R, bar_h / 2)
    star = sd_star5(pu, pv, R)
    shape = np.minimum(circ, bars)
    outer = shape - R / 8.0
    blue = 1 - smoothstep(-aa, aa, outer)
    white_star = 1 - smoothstep(-aa, aa, star)
    white_bars = (1 - smoothstep(-aa, aa, bars)) * smoothstep(-aa, aa, circ)
    white = np.maximum(white_star, white_bars)
    return blue.astype(F32), white.astype(F32)
