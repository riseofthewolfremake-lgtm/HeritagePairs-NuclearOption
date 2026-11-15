"""Heritage Pairs 1.9.12: the two naval liveries of the Nimrod Mk I ("BDF Navy Gray", "PALA Navy"): the numbers, numpy only.

Used by build_textures_nimrod.py (inside Blender) and by tools/stub_tests_1912_nimrod.py (plain python, no bpy), so everything a stub
can judge without a model lives here: the switch, colours, the splinter pattern, marking positions and sizes, the crisp-stencil
coverage, the upper / under blend, the weathering gains, the merge of the two entries into nimrod_liveries.json and the partial
update of the atlas manifest.

Round 2 (review of the first build): the PALA scheme is a straight-edged splinter in the stock PALA navy palette (the same four values
as the FD-32 "PALA Navy Splinter", blender/fd32/textures/naval1912_fd32.py), the BDF scheme speaks the stock VT-7 "BDF Navy Gray"
language (neutral grey, dark navy-grey accent panels, small red warning marks, lighter underside; no royal blue), the number moved
from the fin to the rudder (two tail bracing wires stand in front of the fin), stencils are crisp (sub-sampled and thresholded),
glossiness is the stock naval 0.0 and both carry panel-line / wear detail. Under the pattern and the markings lies one fal grime tile
(assets/textures_nimrod/fal_raw/naval_grime_d.png, fal-ai/z-image/turbo/tiling, record in fal_raw/fal_manifest_1912.jsonl): stains,
drips and scratches, a few per cent, high-passed; pattern geometry, colours and markings are procedural and deterministic.

Colours are numbers read off the stock naval skins' statistics (k-means of the base-colour maps, study file
nuclearoption-ref/study/v1912/stock_naval_ref/stock_naval_stats.json): reference only, no stock pixel is used anywhere.
  BDF  = VT-7 "BDF Navy Gray": grey #6A6969 (37 %), #757372, #5D5C5C, lighter #817E7D, dark navy-grey #35373A (12 %), light #9DA09F
  PALA = EW-25 "PALA Navy Splinter": teal #30464A 35 %, light grey #8E8E8E 30 %, mid grey #5A5A5A 22 %, dark grey #4E4F4F 13 %,
         near-black #1A1A1A (walkways), dark red #701615 (small marks)
Markings: the faction emblems at the six existing sites (faction_marks.py, as on every other livery), the stock titles "NAVY" /
"PALAN" in a dark label plate, a three-digit number on the rudder between two small red arrows, red walkway limit lines and a red
propeller warning line. No real-world insignia.
"""
import json, os, hashlib
import numpy as np

F32 = np.float32
NAVAL_LIVERIES_1912 = True          # False = the bake script knows no naval key (LIVERIES as in 1.9.11)

KEYS = ('bdf_navy', 'pala_navy')
# key, menu name, faction, both factions
ENTRIES = [('bdf_navy', 'BDF Navy Gray', 'BDF', False), ('pala_navy', 'PALA Navy', 'PALA', False)]
GLOSS = 0.0                         # every stock naval livery used as reference has glossiness 0.0 (VT-7 Navy Gray, EW-25 splinter, Ifrit navy)


def rgb(hexs):
    h = hexs.lstrip('#')
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], F32)


# the stock PALA navy splinter palette: MUST equal SCHEME['pala_navy'] of blender/fd32/textures/naval1912_fd32.py (stub-tested)
SPL_PALETTE_HEX = ['#30464A', '#8E8E8E', '#5A5A5A', '#4E4F4F']
SPL_SHARES = [0.35, 0.30, 0.22, 0.13]
LIGHT = np.array([0.90, 0.90, 0.88], F32)          # stencil light (the project's marking white, as the FD-32 naval pair)

SCHEME = {
    'bdf_navy': dict(kind='BDF', pattern='plain', upper=rgb('#6A6969'), metal=rgb('#5D5C5C'), under=rgb('#817E7D'), tape=rgb('#757372'),
                     accent=rgb('#35373A'), walk=rgb('#35373A'), plate=rgb('#35373A'), chip=rgb('#9DA09F'), red=rgb('#8E1A17'),
                     title='NAVY', title_rgb=rgb('#9DA09F'), number='115', number_rgb=LIGHT, keyline=rgb('#35373A')),
    # round 3 (review: the dark #35373A number on the #6A6969 grey was lost in whole-aircraft views): light digits with the dark
    # navy-grey keyline, as the stock navy greys letter in white on grey and as the PALA number beside it
    'pala_navy': dict(kind='PALA', pattern='splinter', palette=[rgb(h) for h in SPL_PALETTE_HEX], shares=SPL_SHARES,
                      walk=rgb('#1A1A1A'), plate=rgb('#1A1A1A'), chip=rgb('#8E8E8E'), red=rgb('#701615') * 1.25,
                      title='PALAN', title_rgb=LIGHT, number='215', number_rgb=LIGHT, keyline=rgb('#1A1A1A')),
}

# ---- marking positions (Blender metres: x span, y forward, z up)
TITLE_Y, TITLE_Z, TITLE_H, TITLE_STROKE = -3.00, 0.04, 0.105, 0.021
TITLE_SEL_Y = (-3.42, -2.58)        # fuselage side texels that may carry the title plate (between the emblem, aft edge y -2.41, and the tailplane root, y -3.72;
                                    # centred there: from 17 degrees aft of the beam the tailplane tip stood in front of the last letter at y -3.21)
PLATE_PAD = (0.045, 0.035)          # label plate: margin round the word (along, up)
PLATE_BORDER = 0.007                # thin light border line inside the plate edge
# the number sits on the RUDDER: the fin carries two bracing wires (nimrod_spec.TAIL_STRUT_Y, y -3.87 and -4.33, up to z 0.91) and the
# rudder post (y -4.47); in a side view they crossed a digit of the first build's fin number (centre y -4.19). Aft of the hinge the
# rudder is clear of all three from any angle up to about 50 degrees off the beam.
NUM_Y, NUM_Z, NUM_H, NUM_STROKE = -4.83, 0.70, 0.15, 0.026
NUM_KEYLINE = 0.010                 # dark keyline round the light digits (PALA: readable on every splinter colour)
ARROW_GAP, ARROW_LEN, ARROW_HALF = 0.035, 0.050, 0.032      # small red arrows fore and aft of the number, pointing at it
RUDDER_HINGE_Y = -4.47
TAIL_WIRE_Y = (-3.87, -4.33)        # nimrod_spec.TAIL_STRUT_Y (stub-tested equal)
CS_HALF = 0.80                      # BDF accent: the upper-wing centre section
WALK_HALF, WALK_Y_FWD = 0.90, 0.23  # walkway: lower-wing top, inboard, aft of the leading-edge sheet
WALK_LINE = 0.018                   # red limit line along the walkway's outer edge
GLARE_Y = (-0.26, 2.20)             # BDF accent: anti-glare panel on top of the metal cowling, cockpit front to the nose ring
GLARE_HALF, GLARE_NZ = 0.20, 0.30   # ... its half width (m): a straight edge in the plan view (a per-face normal test alone gave a saw edge on the cowl facets)
PROP_LINE_Y, PROP_LINE_W = 1.86, 0.022   # red propeller warning line round the cowling (on the cowl panel joint at y 1.86)
UNDER_E0, UNDER_E1 = -0.42, -0.18   # normal.z: below E0 = underside colour, above E1 = upper colour (smoothstep between)

# ---- weathering (restrained: the stock skins' panel-line darkening and edge wear, at this aircraft's scale)
COWL_LINES_Y = (2.27, 1.86, 1.36, 0.86, 0.32, -0.24)   # the metal cowling's panel joints (build_textures_nimrod.features: lines_y)
COWL_LINES_Z = (0.26, -0.32)
PANEL_LINE_HALF, PANEL_LINE_DEPTH = 0.0045, 0.30       # dark joint line: half width (m), darkening at its centre
PANEL_RIM_HALF, PANEL_RIM_GAIN = 0.016, 0.05           # lighter worn rim beside a joint
TAPE_EDGE_OFF, TAPE_EDGE_HALF, TAPE_EDGE_DEPTH = 0.016, 0.004, 0.07   # dirt line each side of a rib tape
TAPE_LIGHT = 0.045                                    # the tape itself, lighter (chalked ridge)
FIN_TAPE_LIGHT, FIN_TAPE_EDGE_DEPTH = 0.015, 0.025    # round 3, fin and rudder: a third of the wing's (review: the regular horizontal
                                                      # tapes every 0.15 m read as scan lines on the plain grey tail)
HINGE_HALF, HINGE_DEPTH = 0.010, 0.35                 # control-surface hinge gaps
GRIME_AMOUNT = 0.055                                  # fal grime tile, multiplicative, +- this (0 = procedural wear only)
GRIME_TILE = 'naval_grime_d'                          # assets/textures_nimrod/fal_raw (fal-ai/z-image/turbo/tiling, seed 191204, fal_manifest.jsonl): stains, drips, smudges, scratches
GRIME_SPAN = 1.70                                     # metres covered by one tile (a stain is 0.1-0.4 m)
GRIME_HP_SIGMA = 48                                   # high-pass of the 512 tile (texels): keeps the stains, drops any tile-wide shading
STREAK_AMOUNT = 0.05
CHIP_MAX = 0.55                                       # edge chips: largest blend toward the chip colour
STENCIL_SUB = 4                                       # stencils: 4 x 4 sub-samples per texel, each thresholded


def text_width(n, h):
    """width of an n-glyph word in the project's stroke font (tex_lib.glyph_segments): (5.6 n - 1.6) h / 6"""
    return (5.6 * n - 1.6) * h / 6.0


def text_box(text, cy, cz, h, stroke):
    """(y_min, y_max, z_min, z_max) of a word centred at (cy, cz), stroke width included"""
    w = text_width(len(text), h)
    return cy - w / 2 - stroke / 2, cy + w / 2 + stroke / 2, cz - h / 2 - stroke / 2, cz + h / 2 + stroke / 2


def plate_half(text):
    """half size (along, up) of the dark label plate behind a title"""
    return text_width(len(text), TITLE_H) / 2 + TITLE_STROKE / 2 + PLATE_PAD[0], TITLE_H / 2 + TITLE_STROKE / 2 + PLATE_PAD[1]


def number_box(text='000', keyline=NUM_KEYLINE):
    """(y_min, y_max, z_min, z_max) of the rudder number INCLUDING its two arrows and the keyline"""
    y0, y1, z0, z1 = text_box(text, NUM_Y, NUM_Z, NUM_H, NUM_STROKE)
    e = ARROW_GAP + ARROW_LEN
    return y0 - e - keyline, y1 + e + keyline, z0 - keyline, z1 + keyline


def interp_table(table, z):
    """piecewise-linear lookup in a [(z, y), ...] table (nimrod_spec.FIN_LE_TABLE, RUDDER_CHORD_TABLE)"""
    zs = [t[0] for t in table]; ys = [t[1] for t in table]
    return float(np.interp(z, zs, ys))


def under_weight(nz):
    """1 on upper / side surfaces, 0 on undersides, smooth between (per-texel face normal z)"""
    t = np.clip((np.asarray(nz, F32) - UNDER_E0) / (UNDER_E1 - UNDER_E0), 0, 1)
    return (t * t * (3 - 2 * t)).astype(F32)


def streak_gain(noise_flow, noise_fine, amount=STREAK_AMOUNT):
    """salt / chalk streaks along the airflow: multiplicative gain round 1.0 from two value noises in 0-1 (one stretched along the
    flight direction, one fine); mean about 1, range 1 +- amount."""
    s = 0.7 * (np.asarray(noise_flow, F32) - 0.5) + 0.3 * (np.asarray(noise_fine, F32) - 0.5)
    return (1.0 + 2.0 * amount * s).astype(F32)


def grime_gain(tile_detail, amount=GRIME_AMOUNT):
    """gain from a zero-mean, unit-std detail sample (the fal tile): clipped at 2.5 sigma, so the gain stays inside 1 +- amount"""
    return (1.0 + amount * np.clip(np.asarray(tile_detail, F32), -2.5, 2.5) / 2.5).astype(F32)


def fal_record():
    """what the bake writes into its stats file about the fal layer"""
    return dict(on=GRIME_AMOUNT > 0, tile=GRIME_TILE, span_m=GRIME_SPAN, amount=GRIME_AMOUNT, endpoint='fal-ai/z-image/turbo/tiling')


def line_gain(d, half, depth):
    """dark line: gain 1 - depth at distance 0, back to 1 beyond about 2 half-widths (gaussian)"""
    return (1.0 - depth * np.exp(-(np.asarray(d, F32) / half) ** 2)).astype(F32)


def rim_gain(d, line_half, rim_half, gain):
    """lighter worn rim beside a joint line: 1 + gain at about one rim half-width from the line, 1 on the line and far away"""
    d = np.asarray(d, F32)
    return (1.0 + gain * np.exp(-((d - line_half * 2.2) / rim_half) ** 2) * (d > line_half)).astype(F32)


# ---------------------------------------------------------------------------------------------- crisp stencils
def supersample(inside, pu, pv, texel, n=STENCIL_SUB):
    """coverage (0-1) of a HARD-edged shape per texel: `inside(pu, pv)` -> bool is evaluated at n x n sub-sample points spread over
    the texel (side `texel` metres, in the mark's own local coordinates) and the hits are averaged: supersample, threshold each
    sample, box filter. The edge is at most one texel wide whatever the stroke width (the first build's stencils used a soft edge of
    half a stroke: five texels)."""
    pu = np.asarray(pu, F32); pv = np.asarray(pv, F32)
    acc = np.zeros(pu.shape, F32)
    offs = ((np.arange(n) + 0.5) / n - 0.5) * texel
    for du in offs:
        for dv in offs:
            acc += np.asarray(inside(pu + F32(du), pv + F32(dv)), F32)
    return acc / float(n * n)


def in_box(pu, pv, hu, hv):
    return (np.abs(pu) <= hu) & (np.abs(pv) <= hv)


def in_frame(pu, pv, hu, hv, inset, width):
    """a rectangular line `width` wide, `inset` inside the edge of the box (hu, hv)"""
    return in_box(pu, pv, hu - inset, hv - inset) & ~in_box(pu, pv, hu - inset - width, hv - inset - width)


def in_arrow(pu, pv, tip_u, length, half, direction):
    """solid triangle: tip at (tip_u, 0) pointing along +pu (direction 1) or -pu (-1), `length` long, base half-height `half`"""
    t = (tip_u - pu) * direction          # 0 at the tip, `length` at the base
    return (t >= 0) & (t <= length) & (np.abs(pv) <= half * t / length)


# ---------------------------------------------------------------------------------------------- integer hash (no tex_lib, no RNG state)
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


# ---------------------------------------------------------------------------------------------- splinter
# The FD-32 "PALA Navy Splinter" pattern (blender/fd32/textures/naval1912_fd32.py, round 2) with the same numbers, so the two
# aircraft are one family on the deck: a jittered triangle mesh in a PLANAR PROJECTION chosen by the surface normal - fuselage
# flanks, fin and rudder in the side view (y, z), wings / tailplane / fuselage top and belly in the plan view (x, y), nose and
# leading edges in the front view (x, z). Every shard edge is a straight segment in its view however round the cowling is (straight
# 3D plane cuts through a round fuselage are ellipses and read as curved bands: the first FD-32 build, and this file's first round-2
# draft). A function of position and normal only: no part name, no UV, so a shard runs unbroken across every part boundary and
# atlas seam of a surface (wing panel / centre section / aileron, fuselage sections, fin / rudder); the pattern changes only where
# the surface turns from one view into another. The Mk I is the FD-32's size (10.3 m span, 7.6 m long, 1.5 m chord): shards
# 0.15-0.5 m, about eight across a wing chord. The functions below are the FD-32 file's, kept equal by a stub test.
SPL_CELL = 0.20                     # lattice cell across (m)
SPL_STRETCH = 1.70                  # cells are longer than wide ...
SPL_ANGLE = 27.0                    # ... and lie at this angle (deg) to the first projection axis
SPL_JITTER = 0.30                   # lattice corners moved by up to this fraction of a cell
SPL_MERGE_QUAD, SPL_MERGE_PAIR = 0.40, 0.30   # share of cells whose two triangles / whose pair of cells are one shard
N_PLANES = 5
_SPL_C, _SPL_S = float(np.cos(np.radians(SPL_ANGLE))), float(np.sin(np.radians(SPL_ANGLE)))
SPL_CUTS = np.cumsum(SPL_SHARES)[:-1]


def plane_of(N):
    """projection plane per point from its unit normal: 0 = right flank (+x), 1 = left flank (-x), 2 = front / rear faces (y),
    3 = upper faces (+z), 4 = lower faces (-z). The largest component decides; x wins a tie over z over y."""
    N = np.asarray(N, np.float64)
    A = np.abs(N)
    side = (A[:, 0] >= A[:, 1]) & (A[:, 0] >= A[:, 2])
    vert = ~side & (A[:, 2] >= A[:, 1])
    return np.where(side, np.where(N[:, 0] >= 0, 0, 1), np.where(vert, np.where(N[:, 2] >= 0, 3, 4), 2)).astype(np.int8)


def plane_uv(P, plane):
    """pattern coordinates (m) of each point in its plane: flanks (y, z), front faces (x, z), upper / lower faces (x, y)"""
    P = np.asarray(P, np.float64)
    return np.where(plane <= 1, P[:, 1], P[:, 0]), np.where(plane >= 3, P[:, 1], P[:, 2])


# ---------------------------------------------------------------------------------------------- round 3: pattern fields by part
# Review of round 2 (renders_r2/naval_nimrod/s_sides.jpg): on the fuselage sides the splinter read as long parallel diagonal bands,
# on the wings as shards. On a wing (plan view) the lattice's long axis runs spanwise, across the flow, over a 1.5 m chord; on the
# flank (side view) it ran ALONG the 7.6 m fuselage, so the stretched, merged cells lined up into bands. Round 3 (the FD-32 file's
# round 3, the same code): the fuselage is one cylindrical unwrap (arc length round the section from the top centreline, and y) in
# which the long axis runs ROUND the fuselage - across the flow, as on the wing - so the shards there have the wing's shape and size;
# the unwrap has no change of view on the fuselage (round 2 switched view facet by facet on the round cowling and turtle deck: saw
# edges) and runs unbroken across fus_engine / fus_center / fus_rear (one seam, the belly centreline). The view is chosen per part
# kind from the smooth (corner) normal; every texel is the area average of the pattern over its own footprint on the surface.
N_FIELDS = 6                        # 0-4 the planar views (plane_of), 5 the fuselage unwrap
FIELD_FUS = 5
KIND_AUTO, KIND_PLAN, KIND_SIDE, KIND_FUS = 0, 1, 2, 3
AUTO_PARTS = ('stab_strut', 'struts_', 'cabane', 'gear_', 'pylon_')          # small / round parts: the view by the largest normal component
PLAN_PARTS = ('wing_', 'aileron_', 'flaperon_', 'stab_', 'elevator_')
SIDE_PARTS = ('fin', 'rudder')
FUS_PARTS = ('fus_', 'spine_', 'canopy_rail')
FUS_FRONT_NY = 0.80                 # fuselage texels whose smooth normal is within ~37 deg of fore / aft (cowl front, tail cone end): front view
FUS_DY, FUS_NTH = 0.05, 72          # unwrap table: y slices of 5 cm, 72 sectors of 5 deg


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
    """a fixed sample of points on the Mk I's main painted surfaces (wing planes, fuselage sides / top / belly, tail), roughly in
    proportion to their area, with the way each faces: what the splinter seed is chosen on (design numbers, no model needed).
    -> (P, N)"""
    def grid(xs, ys, zs, n):
        X, Y, Z = np.meshgrid(xs, ys, zs, indexing='ij')
        P = np.stack([X.ravel(), Y.ravel(), Z.ravel()], -1)
        return P, np.tile(np.asarray(n, np.float64), (len(P), 1))
    L = np.linspace
    parts = [grid(L(-5.1, 5.1, 205), L(-0.20, 1.28, 31), [1.05], (0, 0, 1)), grid(L(-5.1, 5.1, 205), L(-0.20, 1.28, 31), [0.93], (0, 0, -1)),       # upper wing
             grid(L(-4.45, 4.45, 179), L(-1.00, 0.40, 29), [-0.45], (0, 0, 1)), grid(L(-4.45, 4.45, 179), L(-1.00, 0.40, 29), [-0.57], (0, 0, -1)),   # lower wing
             grid([0.40], L(-4.4, 2.3, 135), L(-0.55, 0.50, 22), (1, 0, 0)), grid([-0.40], L(-4.4, 2.3, 135), L(-0.55, 0.50, 22), (-1, 0, 0)),       # fuselage flanks
             grid(L(-0.28, 0.28, 12), L(-4.4, 2.3, 135), [0.55], (0, 0, 1)), grid(L(-0.28, 0.28, 12), L(-4.4, 2.3, 135), [-0.60], (0, 0, -1)),       # fuselage top / belly
             grid(L(-1.55, 1.55, 63), L(-4.85, -3.72, 24), [0.19], (0, 0, 1)), grid(L(-1.55, 1.55, 63), L(-4.85, -3.72, 24), [0.13], (0, 0, -1)),    # tailplane
             grid([0.03], L(-5.2, -3.7, 31), L(0.20, 1.20, 21), (1, 0, 0)), grid([-0.03], L(-5.2, -3.7, 31), L(0.20, 1.20, 21), (-1, 0, 0))]         # fin + rudder
    return np.concatenate([p for p, n in parts]), np.concatenate([n for p, n in parts])


FUS_SAMPLE = (-4.4, 2.3, 0.45, 0.58)  # round 3 sample of the fuselage unwrap: y from, y to, half width, half height (design numbers)


def quad_arc(a, b, t, n=400):
    """arc length of the ellipse (a sin th, b cos th) from th = 0 to t (signed)"""
    th = np.linspace(0.0, t, n)
    d = np.sqrt(a * a * np.cos(th) ** 2 + b * b * np.sin(th) ** 2)
    return float(np.sum((d[1:] + d[:-1]) / 2 * np.diff(th)))


def aircraft_sample_fields():
    """the aircraft sample in round-3 pattern fields -> (field, u, v): wings, tailplane, fin and rudder as aircraft_sample() (their
    fields are the planar views), the fuselage as its unwrap (an elliptic section of the design size, arc length round it, y)"""
    P, N = aircraft_sample()
    y0, y1, a, b = FUS_SAMPLE
    fus = (P[:, 1] >= y0 - 1e-9) & (P[:, 1] <= y1 + 1e-9) & ((np.abs(np.abs(P[:, 0]) - 0.40) < 1e-9) | (np.abs(P[:, 0]) <= 0.28 + 1e-9) & ((np.abs(P[:, 2] - 0.55) < 1e-9) | (np.abs(P[:, 2] + 0.60) < 1e-9)))
    f = plane_of(N)[~fus]
    u, v = plane_uv(P[~fus], f)
    th = np.linspace(-np.pi, np.pi, 63)[:-1]
    s = np.array([quad_arc(a, b, t) for t in th])
    Y, Sx = np.meshgrid(np.linspace(y0, y1, 135), s, indexing='ij')
    return (np.concatenate([f, np.full(Y.size, FIELD_FUS, np.int8)]), np.concatenate([u, Sx.ravel()]), np.concatenate([v, Y.ravel()]))


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


def _splinter_index(P, N, seed, chunk=400000):
    plane = plane_of(N)
    u, v = plane_uv(P, plane)
    return _splinter_index_uv(plane, u, v, seed, chunk)


def shares_of(idx, n):
    idx = np.asarray(idx)
    return [float((idx == i).mean()) for i in range(n)]


def _splinter_seed(shares, tries=24):
    """the pattern seed (0 .. tries-1) whose colour AREA shares on the aircraft sample are nearest the wanted ones (some hundreds of
    shards of very different sizes do not hit the shares by themselves). A constant of the pattern, computed at import. Round 3: on
    the sample in its pattern fields (the fuselage in its unwrap)."""
    f, u, v = aircraft_sample_fields()
    f, u, v = f[::3], u[::3], v[::3]
    best = None
    for s in range(tries):
        d = max(abs(a - b) for a, b in zip(shares_of(_splinter_index_uv(f, u, v, s), len(shares)), shares))
        if best is None or d < best[0] - 1e-12:
            best = (d, s)
    return best[1]


SPL_SEED = _splinter_seed(SPL_SHARES)


def splinter_index(P, N):
    """colour index per point (0 teal, 1 light grey, 2 mid grey, 3 dark grey) from position and unit normal: the triangle of the
    jittered mesh of the point's projection plane, and that shard's colour."""
    return _splinter_index(P, N, SPL_SEED)


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


def splinter_rgb(P, N, palette, texel):
    """colour per texel, hard edges: the pattern is evaluated at four points inside every texel and the palette colours averaged -
    one texel of anti-aliasing on an edge, exactly one palette value anywhere else, nothing blurred.
    -> (rgb (K, 3) float32, index (K,) int8 at the texel centre)"""
    pal = np.asarray(palette, F32)
    out = np.zeros((len(P), 3), F32)
    for Q in aa_points(P, N, texel):
        out += pal[splinter_index(Q, N)]
    return out / F32(len(AA_OFFSETS)), splinter_index(P, N)


def splinter_index_uv(field, u, v):
    return _splinter_index_uv(field, u, v, SPL_SEED)


def splinter_index_at(Q, field, tab=None):
    """round 3: splinter colour index of points Q in the given pattern fields (field_of), the fuselage unwrap table for field 5"""
    u, v = field_coords(Q, field, tab)
    return splinter_index_uv(field, u, v)


def splinter_rgb_fp(P, Ju, Jv, field, tab, palette, texel):
    """round 3: colour per texel = the palette colours averaged over the texel's own footprint on the surface (footprint_mean),
    the pattern in each texel's field. -> (rgb (K, 3) float32, index (K,) int8 at the texel centre)"""
    pal = np.asarray(palette, np.float64)
    col = footprint_mean(lambda Q, sel: pal[splinter_index_at(Q, field[sel], tab)], P, Ju, Jv, texel, 3)
    return col, splinter_index_at(P, field, tab)


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


# ---------------------------------------------------------------------------------------------- files
def merge_liveries(old, new_entries):
    """old: the dict of nimrod_liveries.json (insertion order = list order). new_entries: {key: entry}. Returns a new dict: every
    old key first, unchanged and in its order (a naval key already present keeps its place among the naval keys at the end), then
    the naval keys in KEYS order. Never touches a non-naval entry."""
    out = {k: v for k, v in old.items() if k not in KEYS}
    for k in KEYS:
        if k in new_entries:
            out[k] = new_entries[k]
        elif k in old:
            out[k] = old[k]
    return out


def builder_order(table, naval=True):
    """the list the Unity builder makes from the JSON (NimrodBuild.SaveEverything): for BDF then PALA: the both-faction entries, then
    that side's own - over the entries that are NOT naval; then the naval entries in file order. -> [(name, side), ...]"""
    rows = [(k, e['name'], 'PALA' if 'PALA' in e['faction'].upper() else 'BDF', bool(e.get('both'))) for k, e in table.items()]
    old = [r for r in rows if not r[0].endswith('_navy')]
    nav = [r for r in rows if r[0].endswith('_navy')]
    out = []
    for side in ('BDF', 'PALA'):
        out += [(r[1], side) for r in old if r[3]] + [(r[1], side) for r in old if not r[3] and r[2] == side]
    if naval:
        out += [(r[1], r[2]) for r in nav]
    return out


LIST_1911 = [('FAA Silver (1934)', 'BDF'), ('BDF Matte Gray', 'BDF'), ('BDF Temperate Camo', 'BDF'),
             ('FAA Silver (1934)', 'PALA'), ('PALA Matte Black', 'PALA'), ('PALA Desert Camo', 'PALA')]


def sha12(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()[:12]


def manifest_add(manifest_path, files, model_atlas_hash, written_by):
    """liveries-only bake: record the new files in the atlas manifest WITHOUT rewriting it (atlas_guard.write_manifest would replace
    `written_by` / `note`, which say that the other textures were stamped and not re-baked - still true). Refuses when the model's
    atlas is not the manifest's (then a full re-bake is due). Every existing entry and field stays as it is; the new files are listed
    under `textures` with the manifest atlas, and under `liveries_only_1912` with the script that wrote them."""
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
