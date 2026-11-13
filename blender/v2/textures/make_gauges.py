"""Gauge faces for the B-25H cockpit: 2048^2, 8x8 grid of 256 px cells, cell k = column k % 8,
row k // 8 counted from the BOTTOM of the texture. Layout = the v3 cockpit (blender/v2/b25h_v3_cockpit.py GAUGES,
model contract "Gauges"): dial faces 0-17 without needles where a needle mesh moves, cards 10 (attitude) and 11
(compass), needle textures 62 / 63; all other cells blank panel colour. Original artwork: white markings on black, drawn procedurally (stroke font,
SDF ticks and needles), 2x supersampled.

  blender --background --factory-startup --python blender/v2/textures/make_gauges.py -- [--out <dir>]
"""
import bpy, sys, os, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tex_lib as T

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
out = os.path.abspath(argv[argv.index('--out') + 1]) if '--out' in argv else T.OUT
F32 = np.float32
SS = 2
CELL = 256
C = CELL * SS
v, u = np.mgrid[0:C, 0:C].astype(F32)
PX = (u + 0.5) / C * 2 - 1          # -1..1, +x right
PY = (v + 0.5) / C * 2 - 1          # -1..1, +y up
RR = np.sqrt(PX * PX + PY * PY)
AA = 2.0 / C * 1.0
FACE_R = 0.97
PANEL = np.array([0.075, 0.09, 0.065], F32)
BLACK = np.array([0.025, 0.025, 0.027], F32)
WHITE = np.array([0.93, 0.93, 0.90], F32)
RED = np.array([0.80, 0.12, 0.08], F32)
GREEN = np.array([0.20, 0.62, 0.25], F32)
YEL = np.array([0.90, 0.75, 0.20], F32)


def cover(d):
    return 1 - T.smoothstep(-AA, AA, d)


def capsule(x0, y0, x1, y1, r0, r1):
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy + 1e-12
    t = np.clip(((PX - x0) * dx + (PY - y0) * dy) / L2, 0, 1)
    ex, ey = PX - (x0 + t * dx), PY - (y0 + t * dy)
    return cover(np.sqrt(ex * ex + ey * ey) - (r0 + (r1 - r0) * t))


def polar(a_deg, r):
    a = math.radians(a_deg)
    return r * math.sin(a), r * math.cos(a)      # 0 deg = 12 o'clock, clockwise


def text(img, s, x, y, h, col, w=None, rot=0.0):
    segs, tw = T.glyph_segments(s, h)
    ca, sa = math.cos(rot), math.sin(rot)
    lx = (PX - x) * ca + (PY - y) * sa + tw / 2
    ly = -(PX - x) * sa + (PY - y) * ca + h / 2
    sel = (np.abs(lx - tw / 2) < tw / 2 + h) & (np.abs(ly - h / 2) < h * 1.5)
    if not sel.any():
        return
    d = T.seg_dist(lx[sel], ly[sel], segs)
    cov = cover(d - (w or h * 0.085))
    put(img, sel, cov, col)


def put(img, sel, cov, col):
    if sel is None:
        img[:] = img * (1 - cov[..., None]) + col * cov[..., None]
    else:
        sub = img[sel]
        img[sel] = sub * (1 - cov[:, None]) + col * cov[:, None]


def base_face():
    img = np.tile(PANEL, (C, C, 1))
    put(img, None, cover(RR - FACE_R), np.array([0.13, 0.13, 0.13], F32))
    put(img, None, cover(RR - (FACE_R - 0.035)), BLACK)
    # faint glass sheen
    sheen = np.clip(1 - ((PX + 0.35) ** 2 + (PY - 0.45) ** 2) / 0.25, 0, 1) * 0.05 * cover(RR - FACE_R)
    img += sheen[..., None]
    return img


def dial(img, a0, a1, vmin, vmax, majors, minors=4, labels=None, lab_r=0.62, lab_h=0.13, tick_r=0.88,
         fmt=None, arcs=()):
    def ang(val):
        return a0 + (a1 - a0) * (val - vmin) / (vmax - vmin)
    for lo, hi, col in arcs:
        a = np.degrees(np.arctan2(PX, PY)) % 360
        aa0, aa1 = ang(lo) % 360, ang(hi) % 360
        ins = ((a >= aa0) & (a <= aa1)) if aa0 <= aa1 else ((a >= aa0) | (a <= aa1))
        band = cover(np.abs(RR - (tick_r - 0.02)) - 0.025) * ins
        put(img, None, band, col)
    for k, val in enumerate(majors):
        x0, y0 = polar(ang(val), tick_r)
        x1, y1 = polar(ang(val), tick_r - 0.15)
        put(img, None, capsule(x0, y0, x1, y1, 0.018, 0.018), WHITE)
        if k < len(majors) - 1 and minors:
            for j in range(1, minors + 1):
                vv = val + (majors[k + 1] - val) * j / (minors + 1)
                x0, y0 = polar(ang(vv), tick_r)
                x1, y1 = polar(ang(vv), tick_r - 0.07)
                put(img, None, capsule(x0, y0, x1, y1, 0.009, 0.009), WHITE)
    labels = labels if labels is not None else majors
    for val, lab in zip(majors, labels):
        if lab is None or lab == '':
            continue
        x, y = polar(ang(val), lab_r)
        text(img, str(lab) if fmt is None else fmt(lab), x, y, lab_h, WHITE)
    return ang


def needle(img, a, length=0.8, tail=0.18, w=0.035, col=WHITE):
    x1, y1 = polar(a, length)
    x0, y0 = polar(a + 180, tail)
    put(img, None, capsule(x0, y0, x1, y1, w, w * 0.25), col)
    put(img, None, cover(RR - 0.07), np.array([0.2, 0.2, 0.2], F32))
    put(img, None, cover(RR - 0.035), WHITE * 0.7)


def label(img, s, y=-0.38, h=0.085):
    for k, line in enumerate(s.split('\n')):
        text(img, line, 0.0, y - k * h * 1.5, h, WHITE)


# ------------------------------------------------------------------ gauge kinds
def g_airspeed():
    img = base_face()
    ang = dial(img, 0, 330, 0, 450, list(range(0, 451, 50)), 4, ['', 50, 100, 150, 200, 250, 300, 350, 400, ''],
               lab_h=0.12, arcs=((130, 330, GREEN), (330, 360, YEL)))
    x0, y0 = polar(ang(360), 0.9)
    x1, y1 = polar(ang(360), 0.7)
    put(img, None, capsule(x0, y0, x1, y1, 0.02, 0.02), RED)
    label(img, 'AIR SPEED\nMPH', y=-0.25, h=0.06)
    needle(img, ang(235))
    return img


def g_altimeter():
    img = base_face()
    ang = dial(img, 0, 360, 0, 10, list(range(0, 10)), 4, list(range(0, 10)), lab_h=0.17)
    label(img, 'ALT\nFEET', y=0.3, h=0.07)
    needle(img, ang(7.4) * 1.0, 0.5, 0.12, 0.05)      # thousands
    needle(img, (ang(6.2) * 10) % 360, 0.82, 0.18, 0.03)
    needle(img, ang(0.74), 0.9, 0.0, 0.012)           # ten-thousands pointer
    return img


def g_attitude():
    img = base_face()
    pitch, bank = 0.06, -8.0
    inside = cover(RR - 0.88)
    ca, sa = math.cos(math.radians(bank)), math.sin(math.radians(bank))
    hy = -PX * sa + PY * ca - pitch
    sky = np.array([0.05, 0.07, 0.12], F32)
    gnd = np.array([0.09, 0.065, 0.04], F32)
    put(img, None, inside * (hy > 0), sky)
    put(img, None, inside * (hy <= 0), gnd)
    put(img, None, inside * cover(np.abs(hy) - 0.012), WHITE)
    for a in (-60, -30, -20, -10, 0, 10, 20, 30, 60):
        x0, y0 = polar(a, 0.88)
        x1, y1 = polar(a, 0.76 if a % 30 == 0 else 0.81)
        put(img, None, capsule(x0, y0, x1, y1, 0.015, 0.015), WHITE)
    # miniature aircraft
    put(img, None, capsule(-0.45, -0.02, -0.12, -0.02, 0.022, 0.022), YEL)
    put(img, None, capsule(0.12, -0.02, 0.45, -0.02, 0.022, 0.022), YEL)
    put(img, None, capsule(-0.12, -0.02, 0.0, -0.1, 0.02, 0.02), YEL)
    put(img, None, capsule(0.12, -0.02, 0.0, -0.1, 0.02, 0.02), YEL)
    put(img, None, cover(np.sqrt(PX ** 2 + (PY + 0.02) ** 2) - 0.03), YEL)
    label(img, 'GYRO HORIZON', y=-0.62, h=0.065)
    return img


def g_turnbank():
    img = base_face()
    for a in (-30, 0, 30):
        x0, y0 = polar(a, 0.86)
        x1, y1 = polar(a, 0.7)
        put(img, None, capsule(x0, y0, x1, y1, 0.03 if a else 0.02, 0.03 if a else 0.02), WHITE)
    text(img, 'L', -0.62, 0.42, 0.14, WHITE)
    text(img, 'R', 0.62, 0.42, 0.14, WHITE)
    needle(img, -6, 0.82, 0.0, 0.04)
    # inclinometer tube + ball
    tube_c = (0.0, 0.95)
    rt = np.sqrt((PX - tube_c[0]) ** 2 + (PY - tube_c[1]) ** 2)
    arc = (PY < -0.3) & (np.abs(PX) < 0.45)
    put(img, None, cover(np.abs(rt - 1.55) - 0.085) * arc, np.array([0.25, 0.25, 0.22], F32))
    put(img, None, cover(np.abs(np.abs(PX) - 0.1) - 0.008) * cover(np.abs(rt - 1.55) - 0.09) * (PY < -0.3), WHITE)
    bx = 0.05
    by = tube_c[1] - math.sqrt(1.55 ** 2 - bx ** 2)
    put(img, None, cover(np.sqrt((PX - bx) ** 2 + (PY - by) ** 2) - 0.07), np.array([0.02, 0.02, 0.02], F32))
    label(img, 'TURN', y=-0.2, h=0.07)
    return img


def g_compass(gyro=True):
    img = base_face()
    hdg = 247.0
    for d in range(0, 360, 5):
        a = d - hdg
        x0, y0 = polar(a, 0.86)
        x1, y1 = polar(a, 0.86 - (0.14 if d % 30 == 0 else 0.1 if d % 10 == 0 else 0.05))
        put(img, None, capsule(x0, y0, x1, y1, 0.012, 0.012), WHITE)
    names = {0: 'N', 90: 'E', 180: 'S', 270: 'W'}
    for d in range(0, 360, 30):
        a = d - hdg
        x, y = polar(a, 0.6)
        text(img, names.get(d, str(d // 10)), x, y, 0.12, WHITE, rot=-math.radians(a))
    # lubber line and aircraft symbol
    put(img, None, capsule(0, 0.96, 0, 0.74, 0.02, 0.02), np.array([0.95, 0.5, 0.1], F32))
    put(img, None, capsule(0, -0.25, 0, 0.3, 0.02, 0.02), WHITE)
    put(img, None, capsule(-0.22, 0.1, 0.22, 0.1, 0.02, 0.02), WHITE)
    put(img, None, capsule(-0.1, -0.22, 0.1, -0.22, 0.016, 0.016), WHITE)
    label(img, 'DIR GYRO' if gyro else 'COMPASS', y=-0.36, h=0.05)
    return img


def g_clock():
    img = base_face()
    ang = dial(img, 0, 360, 0, 60, list(range(0, 60, 5)), 4, [12, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11], lab_h=0.16, lab_r=0.63)
    needle(img, (10 + 9 / 60) * 30, 0.5, 0.1, 0.045)
    needle(img, 9 * 6, 0.8, 0.12, 0.03)
    needle(img, 41 * 6, 0.85, 0.2, 0.008, RED)
    label(img, 'CLOCK', y=0.3, h=0.06)
    return img


def g_generic(title, vmin, vmax, step, val, a0=-135, a1=135, minors=4, labels=None, arcs=(), sub=''):
    img = base_face()
    majors = list(np.arange(vmin, vmax + step * 0.5, step))
    labs = labels if labels is not None else [int(m) if float(m).is_integer() else m for m in majors]
    ang = dial(img, a0, a1, vmin, vmax, majors, minors, labs, lab_h=0.13 if len(majors) < 9 else 0.11, arcs=arcs)
    label(img, title + ('\n' + sub if sub else ''), y=-0.2, h=0.062)
    needle(img, ang(val))
    return img


def g_climb():
    img = base_face()
    ang = dial(img, -90, 90, -2, 2, [-2, -1.5, -1, -0.5, 0, 0.5, 1, 1.5, 2], 4, [2, '', 1, '', 0, '', 1, '', 2], lab_h=0.14)
    # mirrored lower half (descent) is the left arc here: label
    text(img, 'UP', 0.5, 0.0, 0.1, WHITE)
    text(img, 'DN', -0.5, 0.0, 0.1, WHITE)
    label(img, 'RATE OF CLIMB\n1000 FT MIN', y=-0.4, h=0.06)
    needle(img, ang(0.4))
    return img


def g_dual(title, vmin, vmax, step, v1, v2, sub=''):
    img = base_face()
    majors = list(np.arange(vmin, vmax + step * 0.5, step))
    ang = dial(img, -135, 135, vmin, vmax, majors, 4, [int(m) for m in majors], lab_h=0.12)
    label(img, title + ('\n' + sub if sub else ''), y=-0.2, h=0.062)
    needle(img, ang(v1))
    needle(img, ang(v2), 0.7, 0.1, 0.03, WHITE * 0.8)
    text(img, '1', *polar(ang(v1), 0.45), 0.09, BLACK)
    return img


# ------------------------------------------------------------------ v3 cockpit layout (model contract 2026-10-30)
# blender/v2/b25h_v3_cockpit.py GAUGES / GAUGE_SCALE: faces 0-17, cards 10/11, needles 62/63. Movable needles and
# cards are separate meshes, so their faces carry NO baked needle; every scale starts at 12 o'clock (angle 0) and
# runs clockwise over the sweep given in GAUGE_SCALE (angle = (value - v0) * sweep / (v1 - v0)).
def face_only(title, sub, vmin, vmax, step, sweep, labels=None, minors=4, arcs=(), a0=0.0, lab_h=None):
    img = base_face()
    majors = list(np.arange(vmin, vmax + step * 0.5, step))
    labs = labels if labels is not None else [int(m) if float(m).is_integer() else m for m in majors]
    dial(img, a0, a0 + sweep, vmin, vmax, majors, minors, labs, lab_h=lab_h or (0.13 if len(majors) < 9 else 0.11),
         arcs=arcs)
    label(img, title + ('\n' + sub if sub else ''), y=-0.3, h=0.062)
    put(img, None, cover(RR - 0.07), np.array([0.2, 0.2, 0.2], F32))          # needle hub well
    return img


def v3_airspeed():
    img = face_only('AIR SPEED', 'MPH', 0, 400, 50, 320, labels=['', 50, 100, 150, 200, 250, 300, 350, 400],
                    arcs=((130, 330, GREEN), (330, 360, YEL)))
    x0, y0 = polar(360 * 320 / 400, 0.9)
    x1, y1 = polar(360 * 320 / 400, 0.7)
    put(img, None, capsule(x0, y0, x1, y1, 0.02, 0.02), RED)
    return img


def v3_altimeter():
    img = base_face()
    dial(img, 0, 360, 0, 10, list(range(0, 10)), 4, list(range(0, 10)), lab_h=0.17)
    label(img, 'ALT\nFEET', y=0.3, h=0.07)
    return img


def v3_attitude_bezel():
    img = base_face()
    for a in (-60, -30, -20, -10, 0, 10, 20, 30, 60):     # bank marks outside the card (card radius 0.86)
        x0, y0 = polar(a, 0.95)
        x1, y1 = polar(a, 0.87)
        put(img, None, capsule(x0, y0, x1, y1, 0.02 if a else 0.03, 0.02 if a else 0.03), WHITE)
    return img


def v3_attitude_card():
    """horizon card: sky over ground, horizon line, pitch ladder (0.0015 m/deg on a 0.036 m card -> 0.0417/deg),
    fixed reference aircraft drawn on the card centre (the card has no separate symbol mesh)."""
    img = np.zeros((C, C, 3), F32)
    sky = np.array([0.10, 0.18, 0.34], F32)
    gnd = np.array([0.20, 0.13, 0.07], F32)
    img[:] = np.where((PY > 0)[..., None], sky, gnd)
    put(img, None, cover(np.abs(PY) - 0.012), WHITE)
    k = 0.0417
    for deg in (-20, -10, 10, 20):
        y = deg * k
        w = 0.28 if abs(deg) == 10 else 0.4
        put(img, None, capsule(-w, y, w, y, 0.009, 0.009), WHITE)
    for deg in (-5, 5, -15, 15):
        put(img, None, capsule(-0.12, deg * k, 0.12, deg * k, 0.007, 0.007), WHITE)
    return img


def v3_heading_bezel():
    img = base_face()
    put(img, None, capsule(0, 0.97, 0, 0.87, 0.025, 0.025), np.array([0.95, 0.5, 0.1], F32))   # lubber line
    for a in (45, 90, 135, 180, 225, 270, 315):
        x0, y0 = polar(a, 0.95)
        x1, y1 = polar(a, 0.89)
        put(img, None, capsule(x0, y0, x1, y1, 0.015, 0.015), WHITE)
    return img


def v3_compass_card():
    img = np.tile(BLACK, (C, C, 1))
    for d in range(0, 360, 5):
        x0, y0 = polar(d, 0.97)
        x1, y1 = polar(d, 0.97 - (0.16 if d % 30 == 0 else 0.11 if d % 10 == 0 else 0.06))
        put(img, None, capsule(x0, y0, x1, y1, 0.013, 0.013), WHITE)
    names = {0: 'N', 90: 'E', 180: 'S', 270: 'W'}
    for d in range(0, 360, 30):
        x, y = polar(d, 0.66)
        text(img, names.get(d, str(d // 10)), x, y, 0.15 if d % 90 == 0 else 0.12,
             np.array([0.95, 0.5, 0.1], F32) if d == 0 else WHITE, rot=-math.radians(d))
    put(img, None, capsule(0, -0.25, 0, 0.3, 0.02, 0.02), WHITE)                 # aircraft symbol
    put(img, None, capsule(-0.22, 0.1, 0.22, 0.1, 0.02, 0.02), WHITE)
    put(img, None, capsule(-0.1, -0.22, 0.1, -0.22, 0.016, 0.016), WHITE)
    return img


def v3_vsi():
    img = base_face()
    dial(img, -170, 170, -6, 6, list(range(-6, 7)), 4, [6, '', 4, '', 2, '', 0, '', 2, '', 4, '', 6], lab_h=0.13)
    text(img, 'UP', 0.42, 0.2, 0.09, WHITE)
    text(img, 'DN', -0.42, 0.2, 0.09, WHITE)
    label(img, 'RATE OF CLIMB\n1000 FT MIN', y=-0.35, h=0.058)
    put(img, None, cover(RR - 0.07), np.array([0.2, 0.2, 0.2], F32))
    return img


def needle_cell(shade=0.93):
    """needle / short-needle texture: the needle mesh samples u,v in [-0.8, 0.9] of the cell; white, darker hub."""
    img = np.tile(WHITE * shade / 0.93, (C, C, 1)).astype(F32)
    put(img, None, cover(RR - 0.35), np.array([0.25, 0.25, 0.25], F32))   # hub cap (disc_uv maps the whole cell)
    put(img, None, cover(RR - 0.18), WHITE * 0.6)
    return img


GAUGES_V3 = {
    0: v3_airspeed,
    1: v3_attitude_bezel,
    2: v3_altimeter,
    3: v3_heading_bezel,
    4: v3_vsi,
    5: lambda: face_only('FUEL', '%', 0, 100, 25, 270, labels=['E', '1/4', '1/2', '3/4', 'F']),
    6: lambda: face_only('MANIFOLD', 'L ENG IN HG', 10, 75, 5, 300, labels=[10, '', 20, '', 30, '', 40, '', 50, '', 60, '', 70, ''],
                         arcs=((25, 46, GREEN),), minors=1),
    7: lambda: face_only('MANIFOLD', 'R ENG IN HG', 10, 75, 5, 300, labels=[10, '', 20, '', 30, '', 40, '', 50, '', 60, '', 70, ''],
                         arcs=((25, 46, GREEN),), minors=1),
    8: lambda: face_only('TACH', 'L ENG RPM X100', 0, 3500, 500, 300, labels=[0, 5, 10, 15, 20, 25, 30, 35],
                         arcs=((1400, 2400, GREEN),)),
    9: lambda: face_only('TACH', 'R ENG RPM X100', 0, 3500, 500, 300, labels=[0, 5, 10, 15, 20, 25, 30, 35],
                         arcs=((1400, 2400, GREEN),)),
    10: v3_attitude_card,
    11: v3_compass_card,
    12: lambda: g_generic('OIL PRESS', 0, 200, 50, 78, sub='LBS', arcs=((70, 90, GREEN),)),
    13: lambda: g_generic('OIL TEMP', -50, 150, 50, 72, sub='DEG C', arcs=((60, 85, GREEN),)),
    14: lambda: g_generic('CYL TEMP', 0, 350, 50, 205, sub='DEG C', arcs=((150, 232, GREEN),)),
    15: lambda: g_generic('HYD PRESS', 0, 2000, 500, 1050, sub='LBS'),
    16: lambda: g_generic('FLAPS', 0, 4, 1, 0.1, labels=['UP', '', '1/2', '', 'DN'], a0=-90, a1=90),
    17: lambda: g_generic('GEAR', 0, 2, 1, 2, labels=['UP', '', 'DN'], a0=-90, a1=90),
    62: needle_cell,
    63: lambda: needle_cell(0.85),
}


# ------------------------------------------------------------------ 1.8.4 (offline C): every dial moves
# The six small dials (12-17) are redrawn WITHOUT their baked needle (a needle mover sits on each now) and nine new faces (18-26) cover the
# dials that were only painted in the fal panel art. Scales from blender/v2/b25h_dials184.SCALES (= the plugin's B25HScales): the scale
# starts at a0 (clockwise from 12 o'clock) and runs over the sweep; the needle rests at 12 o'clock and the plugin turns it to the value.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')))
import b25h_dials184 as D184


def f184(sid, title, sub, step, labels=None, arcs=(), minors=4):
    v0, v1, a0, sw = D184.SCALES[sid]
    return face_only(title, sub, v0, v1, step, sw, labels=labels, minors=minors, arcs=arcs, a0=a0)


def v184_clock():
    img = base_face()
    dial(img, 0, 360, 0, 60, list(range(0, 60, 5)), 4, [12, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11], lab_h=0.16, lab_r=0.63)
    label(img, 'CLOCK', y=0.3, h=0.06)
    put(img, None, cover(RR - 0.07), np.array([0.2, 0.2, 0.2], F32))
    return img


GAUGES_V3.update({
    12: lambda: f184('oil_press', 'OIL PRESS', 'LBS', 50, arcs=((70, 90, GREEN),)),
    13: lambda: f184('oil_temp', 'OIL TEMP', 'DEG C', 50, arcs=((60, 85, GREEN),)),
    14: lambda: f184('cyl_temp', 'CYL TEMP', 'DEG C', 50, arcs=((150, 232, GREEN),)),
    15: lambda: f184('hydraulic', 'HYD PRESS', 'LBS', 500, labels=[0, 5, 10, 15, 20], arcs=((800, 1100, GREEN),)),
    16: lambda: f184('flaps_pos', 'FLAPS', '', 0.25, labels=['UP', '', '1/2', '', 'DN'], minors=1),
    17: lambda: f184('gear_pos', 'GEAR', '', 0.5, labels=['UP', '', 'DN'], minors=1),
    18: v184_clock,
    19: lambda: f184('suction', 'SUCTION', 'IN HG', 2, arcs=((3.75, 5.0, GREEN),)),
    20: lambda: f184('ammeter', 'AMMETER', 'AMPS', 25, labels=[0, '', 50, '', 100, '', 150]),
    21: lambda: f184('carb_temp', 'CARB AIR', 'DEG C', 25, arcs=((15, 38, GREEN),)),
    22: lambda: f184('free_air', 'FREE AIR', 'DEG C', 25),
    23: lambda: f184('deicer', 'DE-ICER', 'LBS', 5, arcs=((7, 10, GREEN),)),
    24: lambda: f184('oxygen', 'OXYGEN', 'LBS', 100, arcs=((400, 450, GREEN),)),
    25: lambda: f184('brake_press', 'BRAKE', 'LBS', 250, labels=[0, '', 5, '', 10, '', 15], arcs=((800, 1100, GREEN),)),
    26: lambda: f184('volts', 'VOLTS', '', 5, arcs=((26, 29, GREEN),)),
})
USED_CELLS = sorted(GAUGES_V3)


def build():
    R = 8 * CELL
    atlas = np.tile(PANEL, (R, R, 1))
    for k, fn in GAUGES_V3.items():
        cell = fn()
        cell = cell.reshape(CELL, SS, CELL, SS, 3).mean(axis=(1, 3))
        # cell k: column k % 8, row k // 8 counted from v = 0; Blender image rows also start at v = 0
        r, c = k // 8, k % 8
        atlas[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL] = cell      # rows already bottom-up (PY = -1 at row 0)
        print('[gauge]', k, flush=True)
    T.save_png(np.clip(atlas, 0, 1), os.path.join(out, 'b25h_gauges.png'))


if __name__ == '__main__':
    build()
