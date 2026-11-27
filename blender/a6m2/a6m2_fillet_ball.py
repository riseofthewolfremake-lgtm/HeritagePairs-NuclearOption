"""r8i (C_rolling_ball): the wing-root fillet as a true variable-radius ROLLING-BALL blend between the fuselage skin and the wing skin.

Why (r8g in game, r8h offline): the fuselage's lower half curves in under the widest line, so above the old fairing's top edge a
down-facing overhang shadowed the root at the map's 40-43 deg sun (stair-stepped shadow band along the fillet-wing line). r8h filled the
crevice by raising a 12-45 deg fairing to the widest line: tall, wide, ragged top edge, lit facet at the front - nothing like the WT bead.

How:
  * Sections ("rows") are taken in planes that contain the span direction (x) and the outward normal of the ROOT wing profile (station
    x = SPINE_X) at a spine point that walks the profile from the lower surface just behind the LE, round the LE nose, along the upper
    surface to the TE, then straight on behind the TE (the fairing past the TE, r1 review). Round the nose the planes rotate with the
    profile normal, so the fillet wraps round the leading edge like the reference bead instead of ending at it.
  * In each plane the fuselage is the curve x = fus_x(n) (the ACTUAL outer ring, body_ring, sampled along the plane's normal axis n) and
    the wing is n = n_w(x) (the analytic station profiles the wing loft is built from). Behind the TE the wing curve of the last on-wing
    row stands in (a virtual floor) and the fairing gets a visible convex underside back into the fuselage.
  * Radius rule per row: the ball's TOP tangent point sits where the fuselage side first tilts more than TILT_DEG off vertical below its
    widest line (a ball tangent at the widest line itself needs a 0.15-0.45 m radius on this round-bottomed body - the r8h fairing again).
    Above that point the side faces outward-and-down by < TILT_DEG, so it is lit by a 41 deg sun and casts no shadow onto the blend (the
    concave blend lies inside the tangent line). Radius clamped to [R_MIN (WT bead), R_MAX], smoothed along the root, tapered at the ends.
  * The ball (centre C, radius r) is solved tangent to both curves; its centre is then moved CROSS_DEG worth toward the corner, so the arc
    CROSSES both skins at ~CROSS_DEG (a clean boolean seam; ROOT_SMOOTH_DEG 35 shades across it, so it reads tangent) instead of grazing
    them (the r8c shards). The arc between the two crossings is the visible fillet: no ragged top edge, no facet, no plate.
  * Each row closes through points buried in the fuselage / wing; the loft is a closed solid boolean-UNIONED into fus_center as before
    (build_a6m2.unify_root), so the root stays ONE mesh and the wells are cut afterwards.
"""
import math
from mathutils import Vector as V
import a6m2_spec as S

K = S.K
TILT_DEG = 32.0      # top tangent: the fuselage side above it tilts <= this off vertical (no down-facing overhang over the blend)
R_MIN = 0.050        # WT bead (~50 mm radius on a near-vertical side)
R_MAX = 0.240
CROSS_DEG = 14.0     # the arc crosses the fuselage / wing skins at this angle (root_junction fails < 8 deg)
NA = 15              # arc points per row
STEP = 0.020         # row spacing along the spine (m)
ROT_STEP = math.radians(3.0)   # and at most this much plane rotation between rows (LE nose)
SPINE_X = 0.45       # the root profile that defines the section planes
S_LOW_END = 0.0      # lower-surface rows (0: the wrap starts at the LE point - under the nose the body bottom sits inside the wing)
FRONT_LEN = 0.35     # spine length (m, + 0.08 m per radian of plane rotation) over which the radius grows from R_END at the nose
R_END = 0.004        # the ball radius at both ends (a rolling ball dies out into the skin-skin corner: no end plate / cap)
AFT_LEN = 0.36       # m behind the TE: the fairing's floor rises AFT_RISE and the radius shrinks to R_END over this length
AFT_RISE = 0.17
AFT_SMOOTH = 0       # r8i build: rows on each side averaged for the aft underside (wavy lower silhouette)
SMOOTH_SIGMA = 0.20  # m along the spine: radius smoothing
END_BURY = (0.15, 0.45, 0.8)   # scale of the first / last rows toward a point inside the solids
INSET = 0.018        # buried return path this far inside the skins
N_LO, N_HI, N_STEP = -0.08, 0.66, 0.004

ROWS = {}            # side letter -> rows (checks_r8.fillet_smooth)
FRAMES = {}          # side letter -> [(spine point, sweep direction)] per row
INFO = []            # per-row diagnostics (right side)


def _sstep(e0, e1, v):
    t = min(max((v - e0) / (e1 - e0), 0.0), 1.0)
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------------------------------------------ fuselage: x of the outer ring at (y, z)
_FC = {}
_FY = 0.002


def _ring(k):
    if k not in _FC:
        import a6m2_parts as AP
        y = k * _FY
        zw = AP.body_params(y)[3]
        r = [q for q in AP.body_ring(y) if q.x >= -1e-9]
        r.sort(key=lambda q: math.atan2(q.z - zw, q.x))
        _FC[k] = ([(q.x, q.z) for q in r], min(q.z for q in r), max(q.z for q in r))
    return _FC[k]


def _ring_x(r, z):
    best = None
    for (ax, az), (bx, bz) in zip(r, r[1:]):
        if (az - z) * (bz - z) <= 0 and abs(bz - az) > 1e-12:
            x = ax + (bx - ax) * (z - az) / (bz - az)
            best = x if best is None else max(best, x)
    return best


def fus_x(y, z):
    """|x| of the fuselage outer skin at (y, z), None where (y, z) is below / above the ring."""
    t = y / _FY
    k0 = math.floor(t); f = t - k0
    xs = []
    for k in (k0, k0 + 1):
        r, zlo, zhi = _ring(k)
        if z < zlo or z > zhi:
            return None
        xs.append(_ring_x(r, z))
    if None in xs:
        return None
    return xs[0] * (1 - f) + xs[1] * f


# ------------------------------------------------------------------------------------------------ wing: station profiles in (y, z)
_WP = {}
_WX = 0.005
_SS = [0.5 * (1 - math.cos(math.pi * k / 120)) for k in range(121)]


def _profile(k):
    if k not in _WP:
        import a6m2_parts as AP
        st = AP.wing_station(k * _WX, 1)
        up = [st.point(s, True) for s in reversed(_SS)]
        lo = [st.point(s, False) for s in _SS[1:]]
        _WP[k] = [(q.y, q.z) for q in up + lo]
    return _WP[k]


def _line_hits(prof, Sy, Sz, Ny, Nz):
    """n of the crossings of the line (Sy, Sz) + n (Ny, Nz) with a closed (y, z) profile."""
    Ty, Tz = -Nz, Ny
    out = []
    d0 = None
    for i in range(len(prof) - 1):
        (ay, az), (by, bz) = prof[i], prof[i + 1]
        da = (ay - Sy) * Ty + (az - Sz) * Tz
        db = (by - Sy) * Ty + (bz - Sz) * Tz
        if da * db <= 0 and abs(db - da) > 1e-12:
            f = da / (da - db)
            qy, qz = ay + (by - ay) * f, az + (bz - az) * f
            out.append((qy - Sy) * Ny + (qz - Sz) * Nz)
    return out


def wing_n(x, Sy, Sz, Ny, Nz):
    """(n of the wing surface on the N side, wing thickness along N) at span x in the plane; None off the wing."""
    t = x / _WX
    k0 = math.floor(t); f = t - k0
    res = []
    for k in (k0, k0 + 1):
        h = _line_hits(_profile(k), Sy, Sz, Ny, Nz)
        if len(h) < 2:
            return None
        res.append((max(h), max(h) - min(h)))
    return (res[0][0] * (1 - f) + res[1][0] * f, res[0][1] * (1 - f) + res[1][1] * f)


# ------------------------------------------------------------------------------------------------ 2D helpers in the plane (x, n)
def _interp(xs, ys, x):
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    lo, hi = 0, len(xs) - 1
    while hi - lo > 1:
        m = (lo + hi) // 2
        if xs[m] <= x:
            lo = m
        else:
            hi = m
    f = (x - xs[lo]) / (xs[hi] - xs[lo])
    return ys[lo] + (ys[hi] - ys[lo]) * f


class Plane:
    def __init__(self, Sy, Sz, Ny, Nz, wcurve=None):
        self.Sy, self.Sz, self.Ny, self.Nz = Sy, Sz, Ny, Nz
        # fuselage curve: n -> x
        self.fn, self.fx = [], []
        n = N_LO
        while n <= N_HI + 1e-9:
            x = fus_x(Sy + n * Ny, Sz + n * Nz)
            if x is not None:
                self.fn.append(n); self.fx.append(x)
            elif self.fn:
                break                     # above the ring top / a gap: stop the curve
            n += N_STEP
        # wing curve: x -> n
        if wcurve is None:
            self.wx, self.wn, self.wt = [], [], []
            x = 0.10
            while x <= 0.95 + 1e-9:
                w = wing_n(x, Sy, Sz, Ny, Nz)
                if w is not None:
                    self.wx.append(x); self.wn.append(w[0]); self.wt.append(w[1])
                x += 0.005
            self.virtual = False
        else:
            self.wx, self.wn, self.wt = wcurve
            self.virtual = True

    def ok(self):
        return len(self.fn) > 10 and len(self.wx) > 10

    def P3(self, x, n, side):
        return V((side * x, self.Sy + n * self.Ny, self.Sz + n * self.Nz))

    def xf(self, n):
        if n < self.fn[0] or n > self.fn[-1]:
            return None
        return _interp(self.fn, self.fx, n)

    def nw(self, x):
        return _interp(self.wx, self.wn, x)

    def thick(self, x):
        return _interp(self.wx, self.wt, x)

    def slope_f(self, n, h=0.006):
        a, b = self.xf(n - h), self.xf(n + h)
        if a is None or b is None:
            return 0.0
        return (b - a) / (2 * h)

    def nF(self, n):
        a = self.slope_f(n)
        L = math.hypot(a, 1.0)
        return (1.0 / L, -a / L)           # outward (+x), tilted down when the side overhangs

    def in_F(self, x, n):
        xf = self.xf(n)
        return xf is not None and x < xf

    def in_W(self, x, n):
        return n < self.nw(x)

    def distW(self, x, n):
        best = 1e9
        bq = (x, self.nw(x))
        wx, wn = self.wx, self.wn
        # coarse window around x
        for i in range(len(wx) - 1):
            ax, an, bx, bn = wx[i], wn[i], wx[i + 1], wn[i + 1]
            if min(ax, bx) > x + 0.6 or max(ax, bx) < x - 0.6:
                continue
            dx, dn = bx - ax, bn - an
            L2 = dx * dx + dn * dn
            t = 0.0 if L2 < 1e-15 else max(0.0, min(1.0, ((x - ax) * dx + (n - an) * dn) / L2))
            px, pn = ax + dx * t, an + dn * t
            d = math.hypot(x - px, n - pn)
            if d < best:
                best = d; bq = (px, pn)
        sgn = 1.0 if n >= self.nw(x) else -1.0
        return sgn * best, bq

    def corner(self):
        prev = None
        for n, x in zip(self.fn, self.fx):
            h = n - self.nw(x)
            if prev is not None and prev[0] < 0 <= h:
                f = -prev[0] / (h - prev[0])
                nn = prev[1] + (n - prev[1]) * f
                return self.xf(nn), nn
            prev = (h, n)
        # no crossing: the fuselage ends above the (virtual) floor - its lowest point
        i = 0
        return self.fx[i], self.fn[i]

    def widest(self, n_c):
        best, bn = -1, None
        for n, x in zip(self.fn, self.fx):
            if n >= n_c and n <= n_c + 0.62 and x > best:
                best, bn = x, n
        return bn

    def r_needed(self, n_T):
        x = self.xf(n_T)
        nx, nn = self.nF(n_T)
        lo, hi = 0.0, 0.8
        if self.distW(x, n_T)[0] <= 0:
            return 0.0
        for _ in range(26):
            r = 0.5 * (lo + hi)
            d, _q = self.distW(x + nx * r, n_T + nn * r)
            if d > r:
                lo = r
            else:
                hi = r
        return 0.5 * (lo + hi)


def spine():
    """[(Sy, Sz, Ny, Nz, tag, s)] from the lower-surface end round the LE, along the upper surface to the TE, then behind the TE."""
    import a6m2_parts as AP
    st = AP.wing_station(SPINE_X, 1)
    fine = []
    for k in (range(400, 0, -1) if S_LOW_END > 0 else ()):   # lower surface s S_LOW_END -> 0
        s = S_LOW_END * (0.5 * (1 - math.cos(math.pi * k / 400)))
        fine.append((st.point(s, False), 'lo', s))
    for k in range(1, 1201):                            # upper 0 -> 1
        s = 0.5 * (1 - math.cos(math.pi * k / 1200))
        if s < 3e-4:
            continue                                     # naca_pts clamps the thickness at the very nose (a flat step)
        fine.append((st.point(s, True), 'up', s))

    def normal(i):
        a = fine[max(i - 1, 0)][0]; b = fine[min(i + 1, len(fine) - 1)][0]
        ty, tz = b.y - a.y, b.z - a.z
        L = math.hypot(ty, tz)
        ny, nz = -tz / L, ty / L
        p, tag, s = fine[i]
        ref_s = max(s, 0.08)
        cu, cl = st.point(ref_s, True), st.point(ref_s, False)
        ry, rz = (cu.y + cl.y) / 2, (cu.z + cl.z) / 2
        if (p.y - ry) * ny + (p.z - rz) * nz < 0:
            ny, nz = -ny, -nz
        return ny, nz
    out = []
    last = None
    for i, (p, tag, s) in enumerate(fine):
        ny, nz = normal(i)
        if last is None:
            out.append((p.y, p.z, ny, nz, tag, s)); last = (p, ny, nz); continue
        dl = math.hypot(p.y - last[0].y, p.z - last[0].z)
        da = math.acos(max(-1.0, min(1.0, ny * last[1] + nz * last[2])))
        if dl >= STEP or da >= ROT_STEP or i == len(fine) - 1:
            out.append((p.y, p.z, ny, nz, tag, s)); last = (p, ny, nz)
    # behind the TE: straight on along the upper surface's last direction
    a, b = fine[-30][0], fine[-1][0]
    dy, dz = b.y - a.y, b.z - a.z
    L = math.hypot(dy, dz); dy, dz = dy / L, dz / L
    ny, nz = out[-1][2], out[-1][3]
    k = 1
    while True:
        y = b.y + dy * STEP * k
        if STEP * k > AFT_LEN + 1e-9:
            break
        out.append((y, b.z + dz * STEP * k, ny, nz, 'aft', STEP * k))
        k += 1
    return out


def _gauss_smooth(vals, pos, sigma):
    out = []
    for i, p in enumerate(pos):
        w = 0.0; a = 0.0
        for j, q in enumerate(pos):
            d = abs(q - p)
            if d > 3 * sigma:
                continue
            g = math.exp(-0.5 * (d / sigma) ** 2)
            w += g; a += g * vals[j]
        out.append(a / w)
    return out


def build_rows(side=1):
    """rows (3D, right side for side 1) + frames. Debug info in INFO."""
    sp = spine()
    planes = []
    last_w = None
    for (Sy, Sz, Ny, Nz, tag, s) in sp:
        if tag == 'aft':
            # behind the TE: the last on-wing row's wing curve as a floor, rising so the fairing lifts into the body side as it ends
            rise = AFT_RISE * _sstep(0.0, AFT_LEN, s)
            pl = Plane(Sy, Sz, Ny, Nz, wcurve=(last_w[0], [w_ + rise for w_ in last_w[1]], last_w[2]))
        else:
            pl = Plane(Sy, Sz, Ny, Nz)
            if pl.ok():
                last_w = (pl.wx, pl.wn, pl.wt)
        planes.append(pl)
    # arc length along the spine
    pos = [0.0]
    for a, b in zip(sp, sp[1:]):
        pos.append(pos[-1] + math.hypot(b[0] - a[0], b[1] - a[1]) + 0.08 * math.acos(max(-1, min(1, a[2] * b[2] + a[3] * b[3]))))
    # 1) tilt-rule radius per row
    raw = []
    cor = []
    for pl in planes:
        if not pl.ok():
            raw.append(None); cor.append(None); continue
        n_c = pl.corner()[1]
        cor.append(n_c)
        n_wd = pl.widest(n_c)
        tmax = math.tan(math.radians(TILT_DEG))
        n_T = n_wd
        n = n_wd
        while n > n_c + 0.004:
            if pl.slope_f(n) > tmax:
                break
            n_T = n
            n -= 0.004
        raw.append(pl.r_needed(n_T))
    good = [r for r in raw if r is not None]
    fill = []
    lastv = good[0]
    for r in raw:
        lastv = r if r is not None else lastv
        fill.append(min(max(lastv, R_MIN), R_MAX))
    rad = _gauss_smooth(fill, pos, SMOOTH_SIGMA)
    # 2) end tapers: lower-surface wrap fades out, aft fairing fades out
    fades = []
    for i, (Sy, Sz, Ny, Nz, tag, s) in enumerate(sp):
        g = _sstep(0.0, FRONT_LEN, pos[i])
        if tag == 'aft':
            g *= 1.0 - _sstep(0.0, AFT_LEN, s)
        rad[i] = R_END + (rad[i] - R_END) * g
        fades.append(1.0)
    # the end rows are scaled into the solids (fully buried end caps: a tiny cap at the skin-skin corner left non-manifold boolean edges)
    for k, f in enumerate(END_BURY):
        fades[k] = min(fades[k], f)
        fades[-1 - k] = min(fades[-1 - k], f)
    # 3) solve each row for its radius, build the arc + buried / underside path
    rows, frames = [], []
    kept_tags = []
    INFO.clear()
    cross = math.radians(CROSS_DEG)
    for i, pl in enumerate(planes):
        Sy, Sz, Ny, Nz, tag, s = sp[i]
        if not pl.ok() or fades[i] <= 0.0:
            continue
        r = rad[i]
        xc_, n_c = pl.corner()
        n_wd = pl.widest(n_c)
        lo, hi = n_c + 0.002, min(n_wd + 0.05, pl.fn[-1] - 0.01)
        if pl.r_needed(hi) < r:
            n_T = hi
            r = pl.r_needed(hi)
        else:
            for _ in range(24):
                m = 0.5 * (lo + hi)
                if pl.r_needed(m) < r:
                    lo = m
                else:
                    hi = m
            n_T = 0.5 * (lo + hi)
        Px, Pn = pl.xf(n_T), n_T
        fx_, fn_ = pl.nF(n_T)
        Cx, Cn = Px + fx_ * r, Pn + fn_ * r
        d, (Qx, Qn) = pl.distW(Cx, Cn)
        wx_, wn_ = (Cx - Qx), (Cn - Qn)
        L = math.hypot(wx_, wn_) or 1.0
        wx_, wn_ = wx_ / L, wn_ / L
        ux, un = fx_ + wx_, fn_ + wn_
        L = math.hypot(ux, un); ux, un = ux / L, un / L
        cu = max(ux * fx_ + un * fn_, 0.2)
        dlt = r * (1 - math.cos(cross)) / cu
        C2x, C2n = Cx - ux * dlt, Cn - un * dlt
        aP = math.atan2(-fn_, -fx_)
        aQ = math.atan2(-wn_, -wx_)
        da = (aQ - aP + math.pi) % (2 * math.pi) - math.pi     # short way round (through the corner side)
        aQ = aP + da                                             # unwrapped (the arc runs aP -> aQ without crossing +-pi)
        amid = aP + da / 2
        sgn = 1.0 if da > 0 else -1.0

        def pt(a):
            return C2x + r * math.cos(a), C2n + r * math.sin(a)
        # walk from the middle to the fuselage, then to the wing
        a_top = aP - sgn * math.radians(25)
        a = amid
        while (a - (aP - sgn * math.radians(40))) * sgn > 0:
            x_, n_ = pt(a)
            if pl.in_F(x_, n_):
                a_top = a; break
            a -= sgn * math.radians(0.25)
        a_foot = aQ + sgn * math.radians(25)
        a = amid
        while (a - (aQ + sgn * math.radians(40))) * sgn < 0:
            x_, n_ = pt(a)
            if pl.in_W(x_, n_):
                a_foot = a; break
            a += sgn * math.radians(0.25)
        a_top -= sgn * math.radians(1.0)          # endpoints 1 deg into the skins: the boolean cuts the seam
        a_foot += sgn * math.radians(1.0)
        arc = [pt(a_top + (a_foot - a_top) * k / (NA - 1)) for k in range(NA)]
        Tx, Tn = arc[0]
        Fx, Fn = arc[-1]
        # buried path (on the wing) / underside (behind the TE)
        th = pl.thick(Fx)
        iw = min(INSET, 0.40 * th) if not pl.virtual else INSET
        on = [(Fx - wx_ * iw, Fn - wn_ * iw),
              (xc_ - fx_ * INSET - wx_ * iw, n_c - fn_ * INSET - wn_ * iw),
              (Tx - fx_ * INSET, Tn - fn_ * INSET)]
        if tag == 'aft':
            w_on = 1.0 - _sstep(0.0, 0.08, s)            # the underside grows out of the TE behind it (r8i: blending ahead of the TE
                                                         # laid it 1.2 mm under the thin TE's lower skin)
        elif tag == 'up':
            w_on = 1.0                                   # on the wing (even the thin TE) the path stays buried
        else:
            w_on = 1.0
        if w_on < 1.0:
            w = max(Fx - xc_, 0.0)
            h = 0.6 * w + 0.004
            nb = n_c - h
            xb = pl.xf(nb)
            if xb is None:
                nb = pl.fn[0]; xb = pl.fx[0]
            xb -= 0.003
            off = []
            for k in range(1, 4):
                a = math.pi / 2 * k / 3
                off.append((xb + (Fx - xb) * math.cos(a), Fn - (Fn - nb) * math.sin(a)))
            path = [(o[0] * (1 - w_on) + p[0] * w_on, o[1] * (1 - w_on) + p[1] * w_on) for o, p in zip(off, on)]
        else:
            path = on
        row2d = arc + path
        f = fades[i]
        if f < 1.0:
            if tag == 'aft':
                ax_, an_ = Tx - fx_ * INSET * 1.5, Tn - fn_ * INSET * 1.5      # inside the body side (no wing under the aft end)
            else:
                ax_, an_ = xc_ - fx_ * INSET - wx_ * iw, n_c - fn_ * INSET - wn_ * iw
            g = max(f, 0.02)
            row2d = [(ax_ + (x_ - ax_) * g, an_ + (n_ - an_) * g) for x_, n_ in row2d]
        rows.append([pl.P3(x_, n_, side) for x_, n_ in row2d]); kept_tags.append(tag)
        frames.append((V((0, Sy, Sz)), V((0, -Nz, Ny)) if tag != 'aft' else V((0, -Nz, Ny))))
        tilt = math.degrees(math.atan(pl.slope_f(n_T)))
        INFO.append(dict(tag=tag, s=round(s, 3), y=round(Sy, 3), z=round(Sz, 3), r=round(r, 3), raw=None if raw[i] is None else round(raw[i], 3),
                         tilt=round(tilt, 1), top=(round(Px, 3), round(Pn, 3)), foot=(round(Fx, 3), round(Fn, 3)), corner=(round(xc_, 3), round(n_c, 3)),
                         fade=round(f, 2), virtual=pl.virtual))
    if AFT_SMOOTH > 0:   # r8i build: off - +-3 rows broke the boolean (open / >2-face edges, canopy gap 11 mm), +-1 changed nothing visible
        # r8i build (C notes: the aft lower silhouette under the TE was slightly wavy - the underside depth follows each row's own
        # foot / corner solution): the underside points of the rows behind the TE are averaged over AFT_SMOOTH rows on each side
        # (same point index; the aft planes are parallel). The arc (visible blend) is left as solved.
        idx = [i for i, t in enumerate(kept_tags) if t == 'aft']
        src_rows = [list(r) for r in rows]
        for i in idx:
            nb = [j for j in range(i - AFT_SMOOTH, i + AFT_SMOOTH + 1) if j in idx]
            for k in range(NA, len(rows[i])):
                rows[i][k] = sum((src_rows[j][k] for j in nb), V()) / len(nb)
    return rows, frames


def fillet_ball(side, L):
    from b25h_geom import MeshBuf, loft, fan_cap, planar_uv
    from b25h_parts import Part
    rows, frames = build_rows(side)
    ROWS[L] = rows; FRAMES[L] = frames
    mb = MeshBuf()
    loft(mb, rows, 'paint', closed=True, outward=True)
    for r, (o, t) in ((rows[0], frames[0]), (rows[-1], frames[-1])):
        tw = t if r is rows[-1] else -t
        # caps: oriented away from the loft (the end rows are faded to a few mm inside the body / wing)
        cen = sum(r, V()) / len(r)
        nxt = sum(rows[1] if r is rows[0] else rows[-2], V()) / len(r)
        tw = (cen - nxt).normalized()
        fan_cap(mb, r, cen, 'paint', tw, uvfunc=lambda p, t_=tw: planar_uv(p, t_))
    return [Part(f'fillet_{L}', 'fus_center', (side * 0.55, -0.6, -0.25), mb, info=dict(kind='fillet'))]
