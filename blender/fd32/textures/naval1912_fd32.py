"""Heritage Pairs 1.9.12: the two naval liveries of the FD-32 ("BDF Navy Hex", "PALA Navy Splinter"): numbers and patterns, numpy only.

Used by build_textures_fd32.py (inside Blender) and by tools/stub_tests_1912_fd32.py (plain python, no bpy): the switch, colours,
the hexagon and splinter patterns, marking positions, the merge of the two entries into fd32_liveries.json and the partial update of
the atlas manifest all live here.

Colours are numbers read off the stock naval skins' statistics (k-means of the base-colour maps, study file
nuclearoption-ref/study/v1912/stock_naval_ref/stock_naval_stats.json): reference only, no stock pixel is used anywhere.
  BDF  = EW-25 Medusa "BDF Navy Hex": blue-grey #61747A / #677981 / #56676C, hexagons navy #344758 (16 %) and near-black #1E1E1D (7 %)
  PALA = EW-25 Medusa "PALA Navy Splinter": teal #30464A 35 %, light grey #8E8E8E 30 %, mid grey #5A5A5A 22 %, dark grey #4E4F4F 13 %

Round 2 (review of the first build: the splinter read as broad soft CURVED bands on the round fuselage - 22 plane cuts through a
cylinder are ellipses, and the cells were metres wide; the hexagons were few, large and soft):
  both patterns are now 2D patterns in a PLANAR PROJECTION chosen by the surface normal (plane_of): fuselage flanks, fin and rudder
  in the side view (y, z), wings / tailplane / fuselage top and belly in the plan view (x, y), noses and leading edges in the front
  view (x, z). An edge that is straight in the pattern is straight on the aircraft seen from that side, however round the fuselage.
  The pattern is a function of position and normal only: it takes no part name and no UV, so it runs unbroken across every part
  boundary and atlas seam of a surface; it changes only where the surface turns from one view into another (the fuselage
  shoulders, a wing root), along a straight line, cross-faded over about two texels (plane_pair). Left / right and upper / lower faces have their own pattern (no mirror image).
  hexagons: 75 mm across flats (13 texels), many small clusters; splinter: jittered triangle mesh, shards 0.15-0.5 m, some merged.
  Edges are hard: the bake supersamples the pattern 4 x per texel (one texel of anti-aliasing), nothing is blurred.
Round 3 (review of round 2: streaks / staircase beside the cockpit and on the belly, the pattern not carried across the fin /
rudder hinge): the view is chosen per PART KIND from the smooth normal (fuselage = one cylindrical unwrap, wings / tail surfaces =
plan view, fin + rudder = side view), every texel is the area average over its own footprint on the surface (atlas Jacobian per
triangle, raster_extra), and the hexagon clusters keep out of the one atlas region that cannot hold them (the cockpit ring, 51 mm
per texel along the fuselage). See the "round 3" blocks below for the measurements.
Nothing random at run time (fixed integer hashes).
Markings: the faction emblems at the six existing sites (faction_marks.py, as on every other livery), the stock titles "NAVY" /
"PALAN" behind the airbrake panel and the green side strip, a three-digit number on both sides of the RUDDER (round 2: on the fin it
sat between the fin strip and the hinge line with the tailplane brace across it in the side view). No real-world insignia.
"""
import json, os, hashlib
import numpy as np

F32 = np.float32
NAVAL_LIVERIES_1912 = True          # False = the bake script knows no naval key (LIVERIES as in 1.9.11)

KEYS = ('bdf_navy', 'pala_navy')
ENTRIES = [('bdf_navy', 'BDF Navy Hex', 'BDF', False), ('pala_navy', 'PALA Navy Splinter', 'PALA', False)]   # key, menu name, faction, both
GLOSS = 0.0                         # round 2: as the stock naval liveries (EW-25 navy LiveryData.Glossiness 0.0); the other FD-32 liveries keep 0.2


def rgb(hexs):
    h = hexs.lstrip('#')
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], F32)


WHITE = np.array([0.90, 0.90, 0.88], F32)
SCHEME = {
    'bdf_navy': dict(kind='BDF', pattern='hex', palette=[rgb('#61747A'), rgb('#344758'), rgb('#1E1E1D')], shares=[0.77, 0.16, 0.07],
                     base2=rgb('#677981'), base3=rgb('#56676C'), title='NAVY', title_rgb=WHITE, number='032', number_rgb=WHITE,
                     outline_rgb=np.array([0.07, 0.08, 0.09], F32)),
    'pala_navy': dict(kind='PALA', pattern='splinter', palette=[rgb('#30464A'), rgb('#8E8E8E'), rgb('#5A5A5A'), rgb('#4E4F4F')],
                      shares=[0.35, 0.30, 0.22, 0.13], title='PALAN', title_rgb=WHITE, number='232', number_rgb=WHITE,
                      outline_rgb=np.array([0.07, 0.08, 0.09], F32)),
}

# ---- marking positions (Blender metres: x span, y forward, z up). The title sits 8 cm further aft than check_naval-liveries.md E.4
# so that "PALAN" (0.57 m) starts behind the airbrake panel (aft edge y -3.05) as well as behind the side strip (ends y -2.90).
TITLE_Y, TITLE_Z, TITLE_H, TITLE_STROKE = -3.40, -0.02, 0.13, 0.022
TITLE_SEL_Y = (-3.80, -3.07)        # fuselage side texels that may carry the title
# round 2: the number is on the RUDDER (y -4.876 .. -5.66 at this height), not on the fin: 0.22 m high, 0.56 m wide, every digit clear
# of the hinge line, of the trailing edge and (in the side view) of the tailplane brace stab_strut_L/R, which ends at y -4.734
RUD_NUM_Y, RUD_NUM_Z, RUD_NUM_H, RUD_NUM_STROKE = -5.265, 0.70, 0.22, 0.034
RUD_HINGE_Y = -4.876                # rudder leading edge = hinge line (measured on the model)
RUD_TE_Y = -5.62                    # rudder trailing edge at the number's upper edge, its nearest point (measured on the model, z 0.85)
STAB_STRUT_AFT_Y = -4.734           # aft end of the tailplane brace in the side view
OUTLINE = 0.008                     # dark keyline round the white lettering (readable on every pattern colour)
TEXT_AA_TEXELS = 0.5                # half-width of the lettering edge in texels (round 2: stencil-crisp; tex_lib's default is half a stroke)
SIDE_STRIP_AFT_Y = -2.90
AIRBRAKE_AFT_Y = -3.05

# ---- hexagons
HEX_FLAT = 0.075                    # across flats (m): 13 texels of the 2048 atlas; ~100 cells along the fuselage
HEX_CLUSTER = (0.50, 0.18)          # the two wavelengths (m) of the cluster noise: many clusters of 3-30 cells
# ---- splinter
SPL_CELL = 0.20                     # lattice cell across (m)
SPL_STRETCH = 1.70                  # cells are longer than wide ...
SPL_ANGLE = 27.0                    # ... and lie at this angle (deg) to the first projection axis
SPL_JITTER = 0.30                   # lattice corners moved by up to this fraction of a cell
SPL_MERGE_QUAD, SPL_MERGE_PAIR = 0.40, 0.30   # share of cells whose two triangles / whose pair of cells are one shard
# ---- fal weathering layer (assets/textures_fd32/fal_raw/naval_grunge.png, fal-ai/z-image/turbo/tiling): cloudy grime, high-passed
# request 01a1db35-f949-7d73-82d8-c776d797a4a4, seed 1665911485; recorded in fal_raw/fal_manifest.jsonl). Pattern geometry, colours and
# markings never come from it. FD32_NAVAL_FAL_WEAR=0 in the environment bakes without it (A/B comparison only; the stats file says which).
FAL_WEAR = os.environ.get('FD32_NAVAL_FAL_WEAR', '1') != '0'
FAL_WEAR_TILE, FAL_WEAR_SPAN, FAL_WEAR_GAIN = 'naval_grunge', 1.30, 0.05


def text_width(n, h):
    """width of an n-glyph word in the project's stroke font (tex_lib.glyph_segments): (5.6 n - 1.6) h / 6"""
    return (5.6 * n - 1.6) * h / 6.0


def text_box(text, cy, cz, h, stroke):
    """(y_min, y_max, z_min, z_max) of a word centred at (cy, cz), stroke width included"""
    w = text_width(len(text), h)
    return cy - w / 2 - stroke / 2, cy + w / 2 + stroke / 2, cz - h / 2 - stroke / 2, cz + h / 2 + stroke / 2


# ---------------------------------------------------------------------------------------------- integer hash noise (no tex_lib)
def ihash(*ints, seed=0):
    """deterministic 32-bit hash of integer arrays -> float in [0, 1)"""
    h = np.full(np.broadcast(*ints).shape, (seed * 0x9E3779B1 + 0x85EBCA6B) & 0xFFFFFFFF, np.uint64)
    for a in ints:
        h = (h ^ (np.asarray(a).astype(np.int64).astype(np.uint64) & np.uint64(0xFFFFFFFF))) * np.uint64(0x9E3779B1) & np.uint64(0xFFFFFFFF)
        h = (h ^ (h >> np.uint64(15))) * np.uint64(0x85EBCA6B) & np.uint64(0xFFFFFFFF)
        h = h ^ (h >> np.uint64(13))
    h = (h * np.uint64(0xC2B2AE35)) & np.uint64(0xFFFFFFFF)
    h = h ^ (h >> np.uint64(16))
    return (h.astype(np.float64) / 4294967296.0)


def vnoise2(u, v, freq, seed):
    """smooth value noise in 2D (bilinear with smoothstep weights between hashed lattice values), 0..1"""
    x = np.asarray(u, np.float64) * freq; y = np.asarray(v, np.float64) * freq
    ix = np.floor(x).astype(np.int64); iy = np.floor(y).astype(np.int64)
    fx = x - ix; fy = y - iy
    fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy)
    a = ihash(ix, iy, seed=seed); b = ihash(ix + 1, iy, seed=seed); c = ihash(ix, iy + 1, seed=seed); d = ihash(ix + 1, iy + 1, seed=seed)
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


# ---------------------------------------------------------------------------------------------- planar projection by the normal
N_PLANES = 5


def plane_of(N):
    """projection plane per point from its unit normal: 0 = right flank (+x), 1 = left flank (-x), 2 = front / rear faces (y),
    3 = upper faces (+z), 4 = lower faces (-z). The largest component decides; x wins a tie over z over y."""
    N = np.asarray(N, np.float64)
    A = np.abs(N)
    side = (A[:, 0] >= A[:, 1]) & (A[:, 0] >= A[:, 2])
    vert = ~side & (A[:, 2] >= A[:, 1])
    return np.where(side, np.where(N[:, 0] >= 0, 0, 1), np.where(vert, np.where(N[:, 2] >= 0, 3, 4), 2)).astype(np.int8)


PLANE_BAND = 0.03     # where the two largest normal components differ by less than this, the two projections are cross-faded


def plane_pair(N, band=PLANE_BAND):
    """-> (first plane = plane_of, second plane = that of the second-largest normal component, weight of the first). The weight is
    1 outside the band and falls linearly to 0.5 where the two components are equal: on the fuselage shoulder (radius ~0.4 m) the
    band is about two texels wide, i.e. the change of projection is an anti-aliased straight line instead of a per-texel staircase."""
    N = np.asarray(N, np.float64)
    A = np.abs(N)
    p1 = plane_of(N)
    ax1 = np.where(p1 <= 1, 0, np.where(p1 == 2, 1, 2))
    A2 = A.copy(); A2[np.arange(len(A)), ax1] = -1.0
    ax2 = np.where((A2[:, 0] >= A2[:, 1]) & (A2[:, 0] >= A2[:, 2]), 0, np.where(A2[:, 2] >= A2[:, 1], 2, 1))
    sgn = N[np.arange(len(N)), ax2] >= 0
    p2 = np.where(ax2 == 0, np.where(sgn, 0, 1), np.where(ax2 == 2, np.where(sgn, 3, 4), 2)).astype(np.int8)
    d = A[np.arange(len(A)), ax1] - A[np.arange(len(A)), ax2]
    return p1, p2, np.clip(0.5 + 0.5 * d / band, 0.5, 1.0)


def plane_uv(P, plane):
    """pattern coordinates (m) of each point in its plane: flanks (y, z), front faces (x, z), upper / lower faces (x, y)"""
    P = np.asarray(P, np.float64)
    return np.where(plane <= 1, P[:, 1], P[:, 0]), np.where(plane >= 3, P[:, 1], P[:, 2])


# ---------------------------------------------------------------------------------------------- round 3: pattern fields by part
# Review of round 2 (renders_r2): beside the cockpit and on the belly the pattern was smeared into long horizontal streaks with
# staircase edges. Measured on the model (study/v1912/renders_r3/naval/diag): (1) the projection was chosen from the FACE normal, so
# on the round fuselage it switched view triangle by triangle (a staircase of facets along each shoulder); (2) the atlas gives the
# FD-32 cockpit section (fus_center, y -1.7 .. -0.6, sides and belly, 1.2 m2) 50.7 mm per texel ALONG the fuselage but 5.6 mm across
# it (a 9 : 1 stretch; elsewhere 5.7 mm both ways), and the pattern was point-sampled 4 x inside a 5.7 mm square, i.e. once per 50 mm
# there: aliasing = streaks. Round 3:
#   - the view is chosen per PART KIND, from the vertex-interpolated (smooth) normal: fuselage = one cylindrical unwrap all round
#     (coordinates: arc length round the fuselage from the top centreline, and y) - no switch of view on the fuselage at all, one seam
#     along the belly centreline; wings / tailplane / control surfaces = the plan view, upper or lower pattern by the normal; fin and
#     rudder = the side view, left or right pattern by the normal (so a shard runs across the hinge line); struts, gear, pylons and the
#     fore / aft facing ends of the fuselage = the old choice by the largest normal component.
#   - every texel is the AREA average of the pattern over its own footprint on the surface (P + a Ju + b Jv, Ju / Jv the 3D size of
#     one texel step in the atlas, measured per triangle): 2 x 2 samples on an ordinary texel, up to FP_MAX along a stretched axis.
#     Where the atlas has few texels the edge is soft along that axis but in the right place and straight - no staircase, no streak.
#   The fuselage unwrap keeps the wing's proportions: on a wing the lattice's long axis runs spanwise (across the flow); on the
#   fuselage it runs round the fuselage (across the flow), so the shards there have the wing's shape and size (Mk I review: the
#   flank pattern read as long parallel diagonal bands because there the long axis ran along the fuselage).
N_FIELDS = 6                        # 0-4 the planar views (plane_of), 5 the fuselage unwrap
FIELD_FUS = 5
KIND_AUTO, KIND_PLAN, KIND_SIDE, KIND_FUS = 0, 1, 2, 3
AUTO_PARTS = ('stab_strut', 'struts_', 'cabane', 'gear_', 'pylon_')          # small / round parts: the view by the largest normal component
PLAN_PARTS = ('wing_', 'aileron_', 'flaperon_', 'stab_', 'elevator_')
SIDE_PARTS = ('fin', 'rudder')
FUS_PARTS = ('fus_', 'spine_', 'canopy_rail')
FUS_FRONT_NY = 0.80                 # fuselage texels whose smooth normal is within ~37 deg of fore / aft (cowl front, tail cone end): front view
FUS_DY, FUS_NTH = 0.05, 72          # unwrap table: y slices of 5 cm, 72 sectors of 5 deg
# The cockpit ring: fus_center y -1.422 .. -0.966 (sides and belly below the sill) has 10 atlas texel rows for its 0.46 m (51 mm per
# texel along the fuselage, measured). A 75 mm hexagon cannot be drawn there at all, so the hexagon clusters keep out of the ring
# (hex_quiet: they thin out over HEX_QUIET_RAMP before it, whole cells only). Splinter shards (0.15-0.5 m) do cross it: their edges
# are in the right place and straight, but an edge across the fuselage axis is soft there (about two of those texels, 0.1 m).
HEX_QUIET_Y = (-1.43, -0.96)
HEX_QUIET_RAMP = 0.20
# (tried and dropped: slowing the splinter down along y inside the ring, so its edges lie flatter to the axis - the bilinear filter
# between rows 50 mm apart then draws those flat edges as a saw tooth of 50 mm steps; the plain area average reads better.)


def kind_of(name):
    """pattern kind of a part from its object name"""
    if name.startswith(AUTO_PARTS):
        return KIND_AUTO
    if name.startswith(PLAN_PARTS):
        return KIND_PLAN
    if name.startswith(SIDE_PARTS):
        return KIND_SIDE
    if name.startswith(FUS_PARTS):
        return KIND_FUS
    return KIND_AUTO


def _fill_periodic(a):
    """fill NaNs along the last axis by linear interpolation, periodically; all-NaN rows stay NaN"""
    out = a.copy()
    n = a.shape[-1]
    for i in range(a.shape[0]):
        ok = np.isfinite(a[i])
        if ok.all() or not ok.any():
            continue
        xs = np.flatnonzero(ok)
        out[i] = np.interp(np.arange(n), np.concatenate([xs - n, xs, xs + n]), np.tile(a[i, xs], 3))
    return out


def _fill_rows(a):
    """fill all-NaN rows by linear interpolation between the nearest filled rows (ends: nearest row)"""
    ok = np.isfinite(a).all(axis=1)
    if ok.all():
        return a
    xs = np.flatnonzero(ok)
    out = a.copy()
    for k in range(a.shape[1]):
        out[:, k] = np.interp(np.arange(len(a)), xs, a[xs, k])
    return out


def _smooth(a, axis, w, periodic):
    k = np.ones(w) / w
    if periodic:
        pad = np.concatenate([np.take(a, range(-(w // 2), 0), axis), a, np.take(a, range(0, w // 2), axis)], axis)
    else:
        pad = np.concatenate([np.repeat(np.take(a, [0], axis), w // 2, axis), a, np.repeat(np.take(a, [-1], axis), w // 2, axis)], axis)
    return np.apply_along_axis(lambda r: np.convolve(r, k, 'valid'), axis, pad)


def fus_table(P):
    """the fuselage unwrap from points on its skin (the bake: every fuselage texel; deterministic). Per 5 cm slice the axis height
    zc = middle of the slice's z range; per 5 degree sector the median distance r from that axis; holes filled, lightly smoothed;
    S = arc length round the section from the top centreline, integral of sqrt(r^2 + (dr/dtheta)^2) dtheta. -> dict"""
    P = np.asarray(P, np.float64)
    y0 = np.floor(P[:, 1].min() / FUS_DY) * FUS_DY
    ny = int(np.ceil((P[:, 1].max() - y0) / FUS_DY)) + 1
    iy = np.clip(((P[:, 1] - y0) / FUS_DY).astype(np.int64), 0, ny - 1)
    zmin = np.full(ny, np.inf); zmax = np.full(ny, -np.inf)
    np.minimum.at(zmin, iy, P[:, 2]); np.maximum.at(zmax, iy, P[:, 2])
    with np.errstate(invalid='ignore'):
        zc = np.where(np.isfinite(zmin), (zmin + zmax) / 2, np.nan)
    ok = np.isfinite(zc)
    zc = np.interp(np.arange(ny), np.flatnonzero(ok), zc[ok])
    zc = _smooth(zc[:, None], 0, 5, False)[:, 0]
    yc = y0 + (np.arange(ny) + 0.5) * FUS_DY
    zp = np.interp(P[:, 1], yc, zc)
    th = np.arctan2(P[:, 0], P[:, 2] - zp)
    r = np.hypot(P[:, 0], P[:, 2] - zp)
    k = np.clip(((th + np.pi) / (2 * np.pi) * FUS_NTH).astype(np.int64), 0, FUS_NTH - 1)
    b = iy * FUS_NTH + k
    o = np.lexsort((r, b))
    bs, rs = b[o], r[o]
    starts = np.flatnonzero(np.r_[True, bs[1:] != bs[:-1]])
    ends = np.r_[starts[1:], len(bs)]
    R = np.full(ny * FUS_NTH, np.nan)
    R[bs[starts]] = rs[(starts + ends - 1) // 2]
    R = _fill_rows(_fill_periodic(R.reshape(ny, FUS_NTH)))
    R = _smooth(_smooth(R, 1, 3, True), 0, 3, False)
    dth = 2 * np.pi / FUS_NTH
    dr = (np.roll(R, -1, 1) - np.roll(R, 1, 1)) / (2 * dth)
    ds = np.sqrt(R * R + dr * dr) * dth                                   # arc length of each sector
    S = np.concatenate([np.zeros((ny, 1)), np.cumsum(ds, 1)], 1)         # at the sector edges, from theta = -pi
    S = S - S[:, FUS_NTH // 2][:, None]                                   # 0 on the top centreline (theta = 0 is an edge)
    return dict(y0=float(y0), ny=ny, zc=zc, yc=yc, S=S)


def fus_coords(P, tab):
    """(s, y) of points on the fuselage: s = arc length round the section from the top centreline (+ to the right, - to the left;
    the seam is the belly centreline), bilinear in the table"""
    P = np.asarray(P, np.float64)
    zp = np.interp(P[:, 1], tab['yc'], tab['zc'])
    th = np.arctan2(P[:, 0], P[:, 2] - zp)
    fy = np.clip((P[:, 1] - tab['y0']) / FUS_DY - 0.5, 0, tab['ny'] - 1)
    i0 = np.floor(fy).astype(np.int64); i1 = np.minimum(i0 + 1, tab['ny'] - 1); wy = fy - i0
    ft = np.clip((th + np.pi) / (2 * np.pi) * FUS_NTH, 0, FUS_NTH)
    k0 = np.minimum(np.floor(ft).astype(np.int64), FUS_NTH - 1); wt = ft - k0
    S = tab['S']
    s0 = S[i0, k0] * (1 - wt) + S[i0, k0 + 1] * wt
    s1 = S[i1, k0] * (1 - wt) + S[i1, k0 + 1] * wt
    return s0 * (1 - wy) + s1 * wy, P[:, 1]


def field_of(N, kind):
    """pattern field per texel from its smooth unit normal and its part kind"""
    N = np.asarray(N, np.float64); kind = np.asarray(kind)
    f = plane_of(N)
    f = np.where(kind == KIND_PLAN, np.where(N[:, 2] >= 0, 3, 4), f)
    f = np.where(kind == KIND_SIDE, np.where(N[:, 0] >= 0, 0, 1), f)
    f = np.where(kind == KIND_FUS, np.where(np.abs(N[:, 1]) >= FUS_FRONT_NY, 2, FIELD_FUS), f)
    return f.astype(np.int8)


def field_coords(P, field, tab=None):
    """pattern coordinates (m) of points in their field: the planar views as plane_uv, the fuselage unwrap (s, y)"""
    field = np.asarray(field)
    u, v = plane_uv(P, np.minimum(field, 4))
    m = field == FIELD_FUS
    if m.any():
        u = u.copy(); v = v.copy()
        u[m], v[m] = fus_coords(np.asarray(P, np.float64)[m], tab)
    return u, v


# ---------------------------------------------------------------------------------------------- hexagons
def hex_cell(u, v, flat=HEX_FLAT):
    """pointy-top hexagon grid, `flat` across flats. -> (q, r) integer axial cell of each point, (cu, cv) the cell centre.
    Cube rounding: every point belongs to the hexagon whose centre is nearest."""
    u = np.asarray(u, np.float64); v = np.asarray(v, np.float64)
    s = flat / np.sqrt(3.0)                       # centre to corner
    qf = (np.sqrt(3.0) / 3.0 * u - v / 3.0) / s
    rf = (2.0 / 3.0 * v) / s
    xf, zf = qf, rf; yf = -xf - zf
    rx, ry, rz = np.round(xf), np.round(yf), np.round(zf)
    dx, dy, dz = np.abs(rx - xf), np.abs(ry - yf), np.abs(rz - zf)
    fix_x = (dx > dy) & (dx > dz); fix_y = ~fix_x & (dy > dz)
    rx = np.where(fix_x, -ry - rz, rx)
    rz = np.where(~fix_x & ~fix_y, -rx - ry, rz)
    q = rx.astype(np.int64); r = rz.astype(np.int64)
    cu = s * np.sqrt(3.0) * (q + r / 2.0); cv = s * 1.5 * r
    return q, r, cu, cv


def _hex_noise(q, r, cu, cv, plane):
    """per CELL: n1 = cluster noise at the cell centre (two wavelengths, ragged cluster outlines), n2 = which cells of a cluster are
    near-black (half smooth, half per-cell: black cells in twos and threes and singly, as on the stock skins). Own field per plane."""
    n1 = 0.55 * vnoise2(cu, cv, 1.0 / HEX_CLUSTER[0], 11 + 7 * plane) + 0.45 * vnoise2(cu, cv, 1.0 / HEX_CLUSTER[1], 23 + 7 * plane)
    n2 = 0.5 * vnoise2(cu, cv, 1.0 / 0.17, 41 + 7 * plane) + 0.5 * ihash(q, r, seed=57 + 7 * plane)
    return n1, n2


def _hex_fields_uv(field, u, v):
    """(q, r, n1, n2) per point from its pattern field and coordinates: its cell and the two noises of that cell"""
    field = np.asarray(field)
    q, r, cu, cv = hex_cell(u, v)
    n1 = np.zeros(len(q)); n2 = np.zeros(len(q))
    for pl in range(N_FIELDS):
        m = field == pl
        if m.any():
            n1[m], n2[m] = _hex_noise(q[m], r[m], cu[m], cv[m], pl)
    m = field == FIELD_FUS                     # round 3: no cluster in the cockpit ring (judged at the cell centre: whole cells only)
    if m.any():
        n1[m] -= hex_quiet(cv[m])
    return q, r, n1, n2


def hex_quiet(y):
    """how much the cluster noise is lowered at fuselage station y: 1 inside the cockpit ring HEX_QUIET_Y, 0 more than HEX_QUIET_RAMP
    outside it, linear between (the clusters thin out toward the ring instead of being cut by its edges)"""
    y = np.asarray(y, np.float64)
    d = np.maximum(HEX_QUIET_Y[0] - y, y - HEX_QUIET_Y[1])                    # < 0 inside the ring
    return np.clip(1.0 - d / HEX_QUIET_RAMP, 0.0, 1.0)


def _hex_fields(P, N, plane=None):
    """(plane, q, r, n1, n2) per point: its projection plane (given, or plane_of(N)), its cell and the two noises of that cell"""
    plane = plane_of(N) if plane is None else np.asarray(plane)
    u, v = plane_uv(P, plane)
    q, r, n1, n2 = _hex_fields_uv(plane, u, v)
    return plane, q, r, n1, n2


def _hex_thresholds(shares):
    """thresholds of the two noises for the wanted colour AREA shares, taken as quantiles of the noise over the aircraft sample (the
    painted surfaces in proportion to their area, each in its own pattern field; round 3: the fuselage in its unwrap): a constant of
    the pattern, computed once at import, no randomness. (Round 2, first try: quantiles of one plane's field over 30 m x 30 m - the
    aircraft itself then came out at 80 / 14 / 6 %.)"""
    f, u, v = aircraft_sample_fields()
    _, _, n1, n2 = _hex_fields_uv(f, u, v)
    dark = shares[1] + shares[2]
    t1 = float(np.quantile(n1, 1.0 - dark))
    t2 = float(np.quantile(n2[n1 > t1], 1.0 - shares[2] / dark))
    return t1, t2


def hex_index_uv(field, u, v):
    """colour index per point (0 base, 1 navy, 2 near-black) from the pattern field and coordinates: a cell is filled when the
    cluster noise AT ITS CENTRE passes the threshold (whole hexagons)."""
    _, _, n1, n2 = _hex_fields_uv(field, u, v)
    return np.where(n1 > HEX_T1, np.where(n2 > HEX_T2, 2, 1), 0).astype(np.int8)


def hex_index(P, N, plane=None):
    """colour index per point (0 base, 1 navy, 2 near-black) from position P (K, 3) and unit normal N (K, 3): the hexagon grid of the
    point's projection plane; a cell is filled when the cluster noise AT ITS CENTRE passes the threshold (whole hexagons)."""
    plane = plane_of(N) if plane is None else np.asarray(plane)
    u, v = plane_uv(P, plane)
    return hex_index_uv(plane, u, v)


# ---------------------------------------------------------------------------------------------- splinter
_SPL_C, _SPL_S = float(np.cos(np.radians(SPL_ANGLE))), float(np.sin(np.radians(SPL_ANGLE)))
SPL_CUTS = np.cumsum(SCHEME['pala_navy']['shares'])[:-1]


def spl_lattice(u, v):
    """pattern metres -> lattice coordinates (cells): turned by SPL_ANGLE, SPL_CELL across, SPL_STRETCH times that along"""
    u = np.asarray(u, np.float64); v = np.asarray(v, np.float64)
    return (_SPL_C * u + _SPL_S * v) / (SPL_CELL * SPL_STRETCH), (-_SPL_S * u + _SPL_C * v) / SPL_CELL


def spl_corner(i, j, seed):
    """the jittered lattice corner (i, j), lattice coordinates"""
    return i + SPL_JITTER * (2 * ihash(i, j, seed=seed + 1) - 1), j + SPL_JITTER * (2 * ihash(i, j, seed=seed + 2) - 1)


def splinter_tri(a, b, seed):
    """the triangle of the jittered mesh that holds each lattice point (a, b): every lattice cell (i, j) is the quad of its four
    jittered corners, cut along one diagonal (by hash) into triangle 0 and 1. -> (i, j, t). All edges are straight segments."""
    a = np.asarray(a, np.float64); b = np.asarray(b, np.float64)
    i0 = np.floor(a).astype(np.int64); j0 = np.floor(b).astype(np.int64)
    V = {}
    for di in range(-1, 3):
        for dj in range(-1, 3):
            V[di, dj] = spl_corner(i0 + di, j0 + dj, seed)
    ti, tj, tt = i0.copy(), j0.copy(), np.zeros(len(a), np.int64)
    found = np.zeros(len(a), bool)

    def inside(p, q, r):
        def e(s, t):
            return (t[0] - s[0]) * (b - s[1]) - (t[1] - s[1]) * (a - s[0])
        return (e(p, q) >= 0) & (e(q, r) >= 0) & (e(r, p) >= 0)
    for di in (0, -1, 1):
        for dj in (0, -1, 1):
            v00, v10, v11, v01 = V[di, dj], V[di + 1, dj], V[di + 1, dj + 1], V[di, dj + 1]
            dg = ihash(i0 + di, j0 + dj, seed=seed + 3) < 0.5
            in0 = np.where(dg, inside(v00, v10, v11), inside(v00, v10, v01))
            in1 = np.where(dg, inside(v00, v11, v01), inside(v10, v11, v01))
            for t, m in ((0, in0), (1, in1)):
                m = m & ~found
                ti[m] = i0[m] + di; tj[m] = j0[m] + dj; tt[m] = t
                found |= m
    return ti, tj, tt


def splinter_colour(i, j, t, seed):
    """colour index 0-3 of triangle (i, j, t): its own hash against the cumulative shares; SPL_MERGE_QUAD of the cells are one shard
    (both triangles the cell's colour), SPL_MERGE_PAIR of the cell pairs (i // 2) are one larger shard."""
    pair = ihash(i // 2, j, seed=seed + 13) < SPL_MERGE_PAIR
    quad = ihash(i, j, seed=seed + 11) < SPL_MERGE_QUAD
    h = np.where(pair, ihash(i // 2, j, seed=seed + 14), np.where(quad, ihash(i, j, seed=seed + 12), ihash(i, j, t, seed=seed + 10)))
    return np.searchsorted(SPL_CUTS, h, side='right').astype(np.int8)


def aircraft_sample():
    """a fixed sample of points on the aircraft's main painted surfaces (wing planes, fuselage sides / top / belly, tail), roughly in
    proportion to their area, with the way each faces: what the splinter seed is chosen on (design numbers of the FD-32, no model
    needed). -> (P, N)"""
    def grid(xs, ys, zs, n):
        X, Y, Z = np.meshgrid(xs, ys, zs, indexing='ij')
        P = np.stack([X.ravel(), Y.ravel(), Z.ravel()], -1)
        return P, np.tile(np.asarray(n, np.float64), (len(P), 1))
    L = np.linspace
    parts = [grid(L(-4.9, 4.9, 197), L(-0.20, 1.28, 31), [1.01], (0, 0, 1)), grid(L(-4.9, 4.9, 197), L(-0.20, 1.28, 31), [0.90], (0, 0, -1)),       # upper wing
             grid(L(-4.4, 4.4, 177), L(-1.00, 0.40, 29), [-0.49], (0, 0, 1)), grid(L(-4.4, 4.4, 177), L(-1.00, 0.40, 29), [-0.60], (0, 0, -1)),    # lower wing
             grid([0.36], L(-3.9, 2.2, 123), L(-0.50, 0.45, 20), (1, 0, 0)), grid([-0.36], L(-3.9, 2.2, 123), L(-0.50, 0.45, 20), (-1, 0, 0)),     # fuselage flanks
             grid(L(-0.25, 0.25, 11), L(-3.9, 2.2, 123), [0.50], (0, 0, 1)), grid(L(-0.25, 0.25, 11), L(-3.9, 2.2, 123), [-0.58], (0, 0, -1)),     # fuselage top / belly
             grid(L(-1.55, 1.55, 63), L(-4.75, -4.10, 14), [0.19], (0, 0, 1)), grid(L(-1.55, 1.55, 63), L(-4.75, -4.10, 14), [0.13], (0, 0, -1)),  # tailplane
             grid([0.03], L(-5.6, -4.0, 33), L(0.20, 1.18, 20), (1, 0, 0)), grid([-0.03], L(-5.6, -4.0, 33), L(0.20, 1.18, 20), (-1, 0, 0))]       # fin + rudder
    return np.concatenate([p for p, n in parts]), np.concatenate([n for p, n in parts])


FUS_SAMPLE = (-3.9, 2.2, 0.45, 0.55)  # round 3 sample of the fuselage unwrap: y from, y to, half width, half height (design numbers)


def aircraft_sample_fields():
    """the aircraft sample in round-3 pattern fields -> (field, u, v): wings, tailplane, fin and rudder as aircraft_sample() (their
    fields are the planar views), the fuselage as its unwrap (an elliptic section of the design size, arc length round it, y)"""
    P, N = aircraft_sample()
    y0, y1, a, b = FUS_SAMPLE
    fus = (P[:, 1] >= y0 - 1e-9) & (P[:, 1] <= y1 + 1e-9) & ((np.abs(np.abs(P[:, 0]) - 0.36) < 1e-9) | (np.abs(P[:, 0]) <= 0.25 + 1e-9) & ((np.abs(P[:, 2] - 0.50) < 1e-9) | (np.abs(P[:, 2] + 0.58) < 1e-9)))
    f = plane_of(N)[~fus]
    u, v = plane_uv(P[~fus], f)
    th = np.linspace(-np.pi, np.pi, 63)[:-1]                                  # as many fuselage points as aircraft_sample() has (62 x 123)
    s = np.array([quad_arc(a, b, t) for t in th])
    Y, Sx = np.meshgrid(np.linspace(y0, y1, 123), s, indexing='ij')
    return (np.concatenate([f, np.full(Y.size, FIELD_FUS, np.int8)]), np.concatenate([u, Sx.ravel()]), np.concatenate([v, Y.ravel()]))


def quad_arc(a, b, t, n=400):
    """arc length of the ellipse (a sin th, b cos th) from th = 0 to t (signed)"""
    th = np.linspace(0.0, t, n)
    d = np.sqrt(a * a * np.cos(th) ** 2 + b * b * np.sin(th) ** 2)
    return float(np.sum((d[1:] + d[:-1]) / 2 * np.diff(th)))


HEX_T1, HEX_T2 = _hex_thresholds(SCHEME['bdf_navy']['shares'])


def _splinter_index_uv(field, u, v, seed, chunk=400000):
    """splinter colour index from the pattern field (0-4 the planar views, 5 the fuselage unwrap) and the pattern coordinates (m)"""
    field = np.asarray(field)
    a, b = spl_lattice(u, v)
    idx = np.zeros(len(a), np.int8)
    for pl in range(N_FIELDS):
        m = np.flatnonzero(field == pl)
        for k in range(0, len(m), chunk):
            s = m[k:k + chunk]
            i, j, t = splinter_tri(a[s], b[s], seed * 16 + pl)
            idx[s] = splinter_colour(i, j, t, seed * 16 + pl)
    return idx


def _splinter_index(P, N, seed, chunk=400000, plane=None):
    plane = plane_of(N) if plane is None else np.asarray(plane)
    u, v = plane_uv(P, plane)
    return _splinter_index_uv(plane, u, v, seed, chunk)


def shares_of(idx, n):
    idx = np.asarray(idx)
    return [float((idx == i).mean()) for i in range(n)]


def _splinter_seed(shares, tries=24):
    """the pattern seed (0 .. tries-1) whose colour AREA shares on the aircraft sample are nearest the wanted ones (some hundreds of
    shards of very different sizes do not hit the shares by themselves). A constant of the pattern, computed at import."""
    f, u, v = aircraft_sample_fields()
    f, u, v = f[::3], u[::3], v[::3]
    best = None
    for s in range(tries):
        d = max(abs(a - b) for a, b in zip(shares_of(_splinter_index_uv(f, u, v, s), len(shares)), shares))
        if best is None or d < best[0] - 1e-12:
            best = (d, s)
    return best[1]


SPL_SEED = _splinter_seed(SCHEME['pala_navy']['shares'])


def splinter_index(P, N, plane=None):
    """colour index per point (0 teal, 1 light grey, 2 mid grey, 3 dark grey) from position and unit normal: the triangle of the
    jittered mesh of the point's projection plane, and that shard's colour."""
    return _splinter_index(P, N, SPL_SEED, plane=plane)


def pattern_index(key, P, N, plane=None):
    return hex_index(P, N, plane) if SCHEME[key]['pattern'] == 'hex' else splinter_index(P, N, plane)


def splinter_index_uv(field, u, v):
    return _splinter_index_uv(field, u, v, SPL_SEED)


def pattern_index_at(key, Q, field, tab=None, ur=None):
    """round 3: colour index of points Q in the given pattern fields (field_of), the fuselage unwrap table for field 5.
    round 4: `ur` (UnderRes, built by the bake from the atlas) lowers the cluster noise of every hexagon cell by its cell quiet value,
    so no cell is drawn on an under-resolved texel (whole cells only); None = round 3 exactly. The splinter index is not changed by it
    (the bake fades the splinter COLOUR instead, fade_to)."""
    u, v = field_coords(Q, field, tab)
    if SCHEME[key]['pattern'] != 'hex':
        return splinter_index_uv(field, u, v)
    if ur is None:
        return hex_index_uv(field, u, v)
    _, _, n1, n2 = _hex_fields_uv(field, u, v)
    n1 = n1 - UR_GAIN * ur.hex_drop(Q, field, u, v)
    return np.where(n1 > HEX_T1, np.where(n2 > HEX_T2, 2, 1), 0).astype(np.int8)


# ---------------------------------------------------------------------------------------------- round 3: texel footprint
FP_MAX = 12          # most samples along one atlas axis of a texel (a 50 mm texel axis gets 12 samples, ~4 mm apart)
FP_CAP = 0.08        # a texel axis longer than this (m; degenerate slivers) is treated as this long


def footprint_counts(Ju, Jv, texel_m):
    """samples along each atlas axis of every texel: 2 on an ordinary texel, ~2 per texel size along a stretched axis, at most FP_MAX"""
    lu = np.minimum(np.linalg.norm(Ju, axis=1), FP_CAP); lv = np.minimum(np.linalg.norm(Jv, axis=1), FP_CAP)
    return (np.clip(np.ceil(2.0 * lu / texel_m - 1e-6), 2, FP_MAX).astype(np.int64),
            np.clip(np.ceil(2.0 * lv / texel_m - 1e-6), 2, FP_MAX).astype(np.int64))


def footprint_mean(fn, P, Ju, Jv, texel_m, channels):
    """area average of fn over each texel's footprint on the surface: fn(Q, sel) -> (len(sel), channels) values at the points Q of the
    texels `sel`; Q = P + a Ju + b Jv on a stratified na x nb grid, a, b in (-1/2, 1/2) (the texel square mapped onto its triangle's
    plane). Ju / Jv are capped at FP_CAP. -> (K, channels) float32"""
    P = np.asarray(P, np.float64); Ju = np.asarray(Ju, np.float64); Jv = np.asarray(Jv, np.float64)
    lu = np.linalg.norm(Ju, axis=1, keepdims=True); lv = np.linalg.norm(Jv, axis=1, keepdims=True)
    Ju = Ju * np.minimum(1.0, FP_CAP / np.maximum(lu, 1e-12)); Jv = Jv * np.minimum(1.0, FP_CAP / np.maximum(lv, 1e-12))
    na, nb = footprint_counts(Ju, Jv, texel_m)
    out = np.zeros((len(P), channels), np.float64)
    key = na * 100 + nb
    for kv in np.unique(key):
        sel = np.flatnonzero(key == kv)
        a_n, b_n = int(kv // 100), int(kv % 100)
        acc = np.zeros((len(sel), channels), np.float64)
        for i in range(a_n):
            for j in range(b_n):
                Q = P[sel] + ((i + 0.5) / a_n - 0.5) * Ju[sel] + ((j + 0.5) / b_n - 0.5) * Jv[sel]
                acc += fn(Q, sel)
        out[sel] = acc / (a_n * b_n)
    return out.astype(F32)


# ---------------------------------------------------------------------------------------------- round 4: under-resolved texels
# In-game round-3 test (study/ingame_1912/r3_test) + offline GPU-sampling simulation (study/v1912/r4_fd32/gpusim.py: BC1 blocks on
# every mip, box mips, bilinear inside the nearest mip, as FD32Build.cs imports the livery): the rows of dark rectangles reported in
# the game are the six exhaust ports per side (fus_engine, material 'exhaust', y 0.33 .. 1.77, z 0.02 .. 0.10; black when the upper
# wing shades them) and the louvre slits (metal_dark), present on every livery since 1.9.11 - geometry, not the texture. What the
# simulation DOES show on the naval textures: wherever one atlas texel is much longer than the 5.7 mm norm (the cockpit ring 51 mm along
# the fuselage, the wing / tail tip caps, the rudder ends, the top of fus_center ahead of the windscreen; 16 532 texels over 19 mm,
# measured) a 75 mm hexagon becomes a 1-2 texel bar, a splinter edge a smeared step, and the fine wear (fal grime, streaks, the
# composite detail) horizontal streaks. Round 4 keeps every pattern edge off those texels:
#   - under-resolution weight per texel from its footprint: L = the longer of its two atlas axes in metres (capped at FP_CAP),
#     0 below UR_OK, 1 above UR_BAD, smoothstep between;
#   - a SPATIAL quiet field (UnderRes.field): the weights deposited in a 3 cm voxel grid of the aircraft, held at full value for
#     UR_MARGIN round them and falling off linearly to 0 over UR_RAMP (chamfer), read trilinearly - a function of 3D position, so
#     it is continuous across atlas seams and part boundaries (no cut along an island edge);
#   - hexagons: per CELL (pattern field, layer, q, r) the largest quiet value over the texel centres inside it lowers the cell's
#     cluster noise (UR_GAIN): a cell touching an under-resolved texel is never filled, cells thin out over the ramp, cells stay whole;
#   - splinter: the shard colour is faded toward the scheme's area-weighted mean colour by the quiet value of the texel (a soft
#     fade over 0.2 m, never a cut);
#   - the fine wear and the composite detail are faded to neutral by the same value (both liveries).
# R4_UNDERRES = False bakes round 3 exactly (stub-tested on the module; the bake script passes ur=None and skips every fade).
# FD32_NAVAL_R4=0 in the environment = False (regression bake only: it must reproduce the round-3 PNGs byte for byte).
R4_UNDERRES = os.environ.get('FD32_NAVAL_R4', '1') != '0'
UR_OK, UR_BAD = 0.012, 0.020        # metres per texel along the longer atlas axis: full pattern below, none above (hexagon 75 mm = 6 / 3.75 texels)
UR_VOXEL, UR_MARGIN, UR_RAMP = 0.03, 0.03, 0.20
UR_GAIN = 1.0                       # cluster-noise drop at quiet 1 (the noise is 0..1: such a cell is never filled)


def smoothstep(e0, e1, x):
    t = np.clip((np.asarray(x, np.float64) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def texel_length(Ju, Jv):
    """metres per texel along the longer of the two atlas axes (each capped at FP_CAP, as footprint_mean)"""
    return np.maximum(np.minimum(np.linalg.norm(np.asarray(Ju, np.float64), axis=1), FP_CAP), np.minimum(np.linalg.norm(np.asarray(Jv, np.float64), axis=1), FP_CAP))


def underres_weight(Ju, Jv):
    """0 = the texel can carry the pattern, 1 = it cannot (see UR_OK / UR_BAD)"""
    return smoothstep(UR_OK, UR_BAD, texel_length(Ju, Jv))


def cell_layer(P, field):
    """which surface a planar-field cell belongs to, so that two surfaces sharing a projection do not share a cell: plan views
    upper wing (z > 0.5) vs lower wing / tailplane; side views struts (|x| > 1.5) vs fin / rudder / cabane. No part straddles either line."""
    P = np.asarray(P, np.float64); f = np.asarray(field)
    plan = (f == 3) | (f == 4); side = (f == 0) | (f == 1)
    return np.where(plan, P[:, 2] > 0.5, np.where(side, np.abs(P[:, 0]) > 1.5, False)).astype(np.int64)


def cell_keys(field, layer, q, r):
    return ((np.asarray(field, np.int64) * 2 + layer) * (1 << 21) + (np.asarray(q, np.int64) + (1 << 20))) * (1 << 21) + (np.asarray(r, np.int64) + (1 << 20))


class UnderRes:
    """round 4 quiet field and per-cell quiet values (see the block comment). P (K, 3) texel centres, w (K,) under-resolution weights;
    field / u / v the texels' pattern fields and coordinates (for the hexagon cells; None = no cell table)."""

    def __init__(self, P, w, field=None, u=None, v=None, voxel=UR_VOXEL, margin=UR_MARGIN, ramp=UR_RAMP):
        P = np.asarray(P, np.float64); w = np.asarray(w, np.float64)
        pad = margin + ramp + 3 * voxel
        self.o = P.min(0) - pad; self.vx = voxel
        n = (np.ceil((P.max(0) + pad - self.o) / voxel)).astype(int) + 1
        G = np.zeros(tuple(n), np.float32)
        s = w > 0
        idx = np.floor((P[s] - self.o) / voxel + 0.5).astype(int)
        np.maximum.at(G, tuple(idx.T), w[s].astype(np.float32))
        m = int(round(margin / voxel))
        for ax in range(3):                                   # hold the full value for `margin` round each deposit (box)
            H = G.copy()
            for k in range(1, m + 1):
                H = np.maximum(H, np.maximum(np.roll(G, k, ax), np.roll(G, -k, ax)))
            G = H
        k = int(np.ceil(ramp / voxel)); step = np.float32(1.0 / k)
        for _ in range(k):                                    # then fall off by 1/k per voxel step (L1 chamfer) over `ramp`
            for ax in range(3):
                G = np.maximum(G, np.maximum(np.roll(G, 1, ax), np.roll(G, -1, ax)) - step)
        self.G = np.clip(G, 0, 1)
        self.n_bad = int(s.sum())
        self.cells = None
        if field is not None:
            q, r, _, _ = hex_cell(u, v)
            keys = cell_keys(field, cell_layer(P, field), q, r)
            val = self.field(P)
            o = np.argsort(keys, kind='stable')
            ks, st = np.unique(keys[o], return_index=True)
            self.cells = (ks, np.maximum.reduceat(val[o], st))

    def field(self, Q):
        """quiet value 0..1 at points Q: trilinear in the voxel grid, smoothstepped"""
        f = (np.asarray(Q, np.float64) - self.o) / self.vx
        i0 = np.clip(np.floor(f).astype(int), 0, np.array(self.G.shape) - 2); t = np.clip(f - i0, 0, 1)
        out = np.zeros(len(f))
        for dx in (0, 1):
            for dy in (0, 1):
                for dz in (0, 1):
                    wgt = (t[:, 0] if dx else 1 - t[:, 0]) * (t[:, 1] if dy else 1 - t[:, 1]) * (t[:, 2] if dz else 1 - t[:, 2])
                    out += wgt * self.G[i0[:, 0] + dx, i0[:, 1] + dy, i0[:, 2] + dz]
        return smoothstep(0.0, 1.0, out)

    def hex_drop(self, Q, field, u, v):
        """per point the quiet value of its hexagon CELL (largest over the texel centres in that cell); a cell no texel centre fell in
        takes the point's own field value"""
        q, r, _, _ = hex_cell(u, v)
        keys = cell_keys(field, cell_layer(Q, field), q, r)
        out = np.full(len(keys), np.nan)
        if self.cells is not None:
            ks, vs = self.cells
            i = np.clip(np.searchsorted(ks, keys), 0, len(ks) - 1)
            hit = ks[i] == keys
            out[hit] = vs[i[hit]]
        miss = np.isnan(out)
        if miss.any():
            out[miss] = self.field(np.asarray(Q, np.float64)[miss])
        return out


def plain_colour(key):
    """the colour a faded pattern goes to: the scheme's palette weighted by its area shares (same encoding as the palette)"""
    c = SCHEME[key]
    return (np.stack(c['palette']).astype(np.float64) * np.asarray(c['shares'], np.float64)[:, None]).sum(0).astype(F32)


def fade_to(x, target, q):
    """x faded toward target by q (0 = x, 1 = target); x (K,) or (K, C)"""
    x = np.asarray(x, np.float64); q = np.asarray(q, np.float64)
    if x.ndim == 2:
        q = q[:, None]
    return x * (1 - q) + np.asarray(target, np.float64) * q


def raster_extra(objects, R):
    """round 3, inside Blender: the same rasterisation as the bake scripts' rasterise() (same objects, triangles, texel test and write
    order, so the same last writer per texel) but writing, per texel, the Jacobian of its triangle (Ju, Jv = metres per texel step
    along the atlas x / y) and the smooth normal (corner normals interpolated). -> (Ju, Jv, smooth normal, part id) as (R, R, 3) /
    (R, R) arrays; the caller compares the part ids with rasterise()'s."""
    import math
    Ju = np.zeros((R, R, 3), F32); Jv = np.zeros((R, R, 3), F32); sn = np.zeros((R, R, 3), F32); pid = np.full((R, R), -1, np.int16)
    k = -1
    for ob in objects:
        if ob.type != 'MESH':
            continue
        me = ob.data
        mats = [m.name if m else '' for m in me.materials]
        if 'paint' not in mats:
            continue
        pi = mats.index('paint')
        k += 1
        uv = me.uv_layers['livery'].data
        M = ob.matrix_world; N3 = M.to_3x3().inverted().transposed()
        me.calc_loop_triangles()
        cn = me.corner_normals
        for lt in me.loop_triangles:
            if lt.material_index != pi:
                continue
            P = [M @ me.vertices[v].co for v in lt.vertices]
            U = [uv[l].uv for l in lt.loops]
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
            Pa = np.array([tuple(p) for p in P], np.float64)
            dU = np.array([[bx - ax, cx - ax], [by - ay, cy - ay]], np.float64)
            J = np.stack([Pa[1] - Pa[0], Pa[2] - Pa[0]], 1) @ np.linalg.inv(dU)      # (3, 2): d position / d texel x, y
            Na = np.array([tuple((N3 @ cn[l].vector).normalized()) for l in lt.loops], np.float64)
            W = np.stack([w0[ins], w1[ins], w2[ins]], -1).astype(np.float64)
            n = W @ Na
            n /= np.maximum(np.linalg.norm(n, axis=1), 1e-12)[:, None]
            yy, xx = gy[ins].astype(int), gx[ins].astype(int)
            Ju[yy, xx] = J[:, 0]; Jv[yy, xx] = J[:, 1]
            sn[yy, xx] = n
            pid[yy, xx] = k
    return Ju, Jv, sn, pid


AA_OFFSETS = ((0.125, 0.375), (-0.375, 0.125), (-0.125, -0.375), (0.375, -0.125))   # rotated-grid 4 x supersampling, in texels


def tangents(N):
    """two unit vectors in the surface at each point (perpendicular to the unit normal and to each other)"""
    N = np.asarray(N, np.float64)
    ref = np.where((np.abs(N[:, 2]) < 0.9)[:, None], np.array([0.0, 0.0, 1.0]), np.array([0.0, 1.0, 0.0]))
    t1 = np.cross(ref, N); t1 /= np.maximum(np.linalg.norm(t1, axis=1), 1e-12)[:, None]
    return t1, np.cross(N, t1)


def aa_points(P, N, texel_m):
    """the four supersampling positions of every texel: its 3D point moved in the surface by AA_OFFSETS x the texel size (m)"""
    t1, t2 = tangents(N)
    P = np.asarray(P, np.float64)
    return [P + texel_m * (a * t1 + b * t2) for a, b in AA_OFFSETS]


def streak_gain(noise_flow, noise_fine, amount=0.04):
    """salt / chalk streaks along the airflow: multiplicative gain round 1.0 from two noises in 0-1"""
    s = 0.7 * (np.asarray(noise_flow, F32) - 0.5) + 0.3 * (np.asarray(noise_fine, F32) - 0.5)
    return (1.0 + 2.0 * amount * s).astype(F32)


# ---------------------------------------------------------------------------------------------- files
def merge_liveries(old, new_entries):
    """old: the dict of fd32_liveries.json (insertion order = file order). Returns a new dict: every non-naval key first, unchanged
    and in its order, then the naval keys in KEYS order (a new entry replaces an old naval one). Never touches a non-naval entry."""
    out = {k: v for k, v in old.items() if k not in KEYS}
    for k in KEYS:
        if k in new_entries:
            out[k] = new_entries[k]
        elif k in old:
            out[k] = old[k]
    return out


def builder_order(table, naval=True):
    """the list FD32Build.SaveEverything makes from the JSON: for BDF then PALA that side's own entries in file order, over the
    entries that are NOT naval (the 1.9.11 loop); then, appended, the naval entries BDF first. -> [(name, side), ...]"""
    rows = [(k, e['name'], 'PALA' if 'PALA' in e['faction'].upper() else 'BDF') for k, e in table.items()]
    old = [r for r in rows if not r[0].endswith('_navy')]
    nav = [r for r in rows if r[0].endswith('_navy')]
    out = []
    for side in ('BDF', 'PALA'):
        out += [(r[1], side) for r in old if r[2] == side]
    if naval:
        for side in ('BDF', 'PALA'):
            out += [(r[1], side) for r in nav if r[2] == side]
    return out


LIST_1911 = [('BDF Matte Gray', 'BDF'), ('BDF Temperate Camo', 'BDF'), ('PALA Desert Camo', 'PALA'), ('PALA Matte Black', 'PALA')]
LIST_1912 = LIST_1911 + [('BDF Navy Hex', 'BDF'), ('PALA Navy Splinter', 'PALA')]


def sha12(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()[:12]


def manifest_add(manifest_path, files, model_atlas_hash, written_by):
    """liveries-only bake: record the new files in the atlas manifest WITHOUT rewriting it (atlas_guard.write_manifest would replace
    `written_by` / `note`, which say that the other textures were stamped and not re-baked - still true, and stub_tests_1816o reads
    them). Refuses when the model's atlas is not the manifest's (then a full re-bake is due). Every existing entry and field stays;
    the new files are listed under `textures` with the manifest atlas, and under `liveries_only_1912` with the script that wrote them."""
    m = json.load(open(manifest_path))
    if model_atlas_hash != m['atlas_hash']:
        raise RuntimeError(f'model atlas {model_atlas_hash} != manifest atlas {m["atlas_hash"]}: liveries-only is not valid, run the full bake')
    tex = dict(m['textures'])
    for f in files:
        tex[os.path.basename(f)] = dict(sha=sha12(f), atlas=m['atlas_hash'])
    m['textures'] = dict(sorted(tex.items()))
    m['liveries_only_1912'] = dict(written_by=written_by, files=sorted(os.path.basename(f) for f in files))
    with open(manifest_path, 'w') as fh:
        json.dump(m, fh, indent=1)
    return m
