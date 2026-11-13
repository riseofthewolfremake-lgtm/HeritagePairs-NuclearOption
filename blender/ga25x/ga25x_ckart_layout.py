"""GA-25X 0.3.2 cockpit panel-art atlas layout (shared by the atlas builder and the cockpit generator).

Atlas: assets/textures_ga25x/ga25x_ckart_b.png (+ _n), ATLAS x ATLAS px, built by blender/ga25x/textures/make_cockpit_art_ga25x.py
from the fal-generated panel art in assets/textures_ga25x/fal_raw_cockpit/ (our own generated art, see assets/fal_manifest.jsonl).
Each entry: atlas rect (x0, y0, x1, y1) in px, image row 0 at the TOP; source file and source crop (px, row 0 top) or None = whole.
uv(name, u, v) maps a 0-1 coordinate inside the panel (u -> right, v -> up) to atlas UV (Blender/Unity: v = 0 at the bottom).
"""
ATLAS = 4096
PAD = 8
PANELS = {
    # name              atlas rect                   source                 source crop (None = whole image)
    'console_left':   ((0, 0, 1792, 1202),          'console_left.png',    None),
    'console_right':  ((1800, 0, 3592, 1202),       'console_right.png',   None),
    'pedestal_gate':  ((3600, 0, 4096, 728),        'v034/quadrant_gate.png', None),             # 0.3.4: fal art made for the slot layout
    'pedestal_radio': ((3600, 736, 4096, 1210),     'pedestal.png',        (0, 1240, 1696, 2528)),  # radios / IFF (lower half)
    'mfd_bezel':      ((0, 1210, 2272, 2478),       'mfd_bezel.png',       None),
    'placard_danger': ((2280, 1210, 2900, 1580),    'placards.png',        (57, 84, 812, 544)),
    'placard_data':   ((2910, 1210, 3500, 1580),    'placards.png',        (912, 88, 1640, 540)),
    'placard_canopy': ((3510, 1210, 4096, 1580),    'placards.png',        (1743, 88, 2470, 540)),
    'placard_nostep': ((2280, 1590, 3060, 1910),    'placards.png',        (912, 651, 1877, 1046)),
    'placard_glimit': ((3070, 1590, 3560, 1910),    'placards.png',        (1819, 1187, 2470, 1609)),
    'placard_fuel':   ((3570, 1590, 4096, 1910),    'placards.png',        (57, 1199, 827, 1609)),
    'annunciator':    ((0, 2486, 4096, 2978),       'annunciator.png',     None),
    'subpanel':       ((0, 2986, 2040, 3492),       'subpanel_strip.png',  None),
    'breakers':       ((2048, 2986, 4088, 3492),    'breakers.png',        None),
    # plain panel stock: a blank, riveted strip cut from the left console border (used for unlabelled panel faces)
    'blank':          ((0, 3500, 1200, 4096),       'console_right.png',   (770, 960, 1190, 1570)),
}
# MFD bezel opening inside the bezel art (measured from mfd_bezel.png: dark run x 264..2487 of 2752, y 230..1305 of 1536)
BEZEL_OPEN = (264 / 2752, 1 - 1305 / 1536, 2487 / 2752, 1 - 230 / 1536)   # (u0, v0, u1, v1), v up


def uv(name, u, v):
    (x0, y0, x1, y1), _, _ = PANELS[name]
    x0, y0, x1, y1 = x0 + 2, y0 + 2, x1 - 2, y1 - 2         # stay inside the rect (bleed)
    return ((x0 + u * (x1 - x0)) / ATLAS, 1.0 - (y0 + (1.0 - v) * (y1 - y0)) / ATLAS)


def aspect(name):
    (x0, y0, x1, y1), _, crop = PANELS[name]
    return (x1 - x0) / (y1 - y0)


# 0.3.4 throttle quadrant gate (v034/quadrant_gate.png, fal edit of the layout guide v034/quadrant_layout_guide.png): measured
# landmarks of the generated art (make_cockpit_art_ga25x.measure_quadrant re-measures them on every build and fails if the art
# moved by > 4 px). Image 1856 x 2304, row 0 at the top. The cockpit generator maps the art piecewise-linearly through these:
#   u: x = -hx -> 0, slot left edge -> QG_SLOT_U[0], slot right edge -> QG_SLOT_U[1], +hx -> 1
#   v: arc start -62 deg -> 0, slot bottom -54 -> v(row 2070), IDLE tick -46 -> v(row 1866), MAX tick +6 -> v(row 555),
#      slot top +13 -> v(row 381), arc end +28 -> 1   (IDLE at the lever's 0 deg angle, MAX at 52 deg)
QG_SIZE = (1856, 2304)
QG_SLOT_PX = (734, 1124, 381, 2071)          # dark opening: x0, x1, row top, row bottom
QG_TICK_ROWS = {'MAX': 555, 'MIL': 883, 'IDLE': 1866}
QG_SLOT_U = (QG_SLOT_PX[0] / QG_SIZE[0], QG_SLOT_PX[1] / QG_SIZE[0])


def qg_v(row):
    return 1.0 - row / QG_SIZE[1]


QG_V_KNOTS = [(-62.0, 0.0), (-54.0, qg_v(QG_SLOT_PX[3])), (-46.0, qg_v(QG_TICK_ROWS['IDLE'])), (6.0, qg_v(QG_TICK_ROWS['MAX'])),
              (13.0, qg_v(QG_SLOT_PX[2])), (28.0, 1.0)]
