"""Hawker Nimrod Mk I cockpit v2: shared layout table (pure Python: no bpy / mathutils).

Used by blender/nimrod/nimrod_cockpit.py (geometry, UVs) and blender/nimrod/textures/make_cockpit_art_nimrod.py (PIL/numpy art),
so the painted dial faces, placards and panel labels always line up with the geometry.

Layout sources (references only, nothing copied): refs\\nimrod_cockpit_user\\50.png (real Nimrod/Hart panel) for the panel,
51-55 (game views of another Nimrod cockpit) for the walls, floor and seat. Sizes were estimated from photo 50 with the lower
panel width as the scale bar (~525 px = 0.77 m, ~1.47 mm/px) and the opening measured on our fuselage (front arch at y -0.40,
top z 0.60; sills z 0.50 at x +-0.30; rear arch y -1.05).

Frames
  world: Blender x right, y forward, z up (metres).
  panel: (x, h, off) - x right, h up the panel plane from its bottom edge, off toward the pilot. See panel_point().
"""
import math

# ------------------------------------------------------------------------------------------- panel plane
PANEL_Y0 = -0.355          # y of the lower panel face at its bottom edge
PANEL_Z0 = 0.100           # z of the lower panel bottom edge
TILT_DEG = 3.0             # top leans forward
LOWER = dict(x0=-0.385, x1=0.385, h0=0.0, h1=0.235, r=0.030, thick=0.006)
TUBE_H, TUBE_OFF, TUBE_R = 0.235, 0.024, 0.011          # black cross tube in front of the lower panel's top edge
DIAG = [((-0.135, 0.235), (-0.352, 0.035)), ((0.135, 0.235), (0.352, 0.035))]   # diagonal tubes of the cross-frame
UPPER_OFF = 0.014          # raised centre section stands proud of the lower panel
UPPER = dict(h0=0.200, shoulder_h=0.345, half_w=0.123, neck_w=0.058, neck_top=0.462, r=0.018)


def upper_outline(k=8):
    """raised centre section outline (x, h), counter-clockwise: wide body with the two big dials, narrow neck with a round top."""
    U = UPPER
    hw, nw, sh, r = U['half_w'], U['neck_w'], U['shoulder_h'], U['r']
    pts = [(-hw, U['h0']), (hw, U['h0'])]
    for i in range(k + 1):                          # right shoulder corner (rounded)
        a = math.radians(0 + 90 * i / k)
        pts.append((hw - r + r * math.cos(a), sh - r + r * math.sin(a)))
    for i in range(1, k):                           # concave fillet into the neck
        a = math.radians(-90 - 90 * i / k)
        pts.append((nw + r + r * math.cos(a), sh + r + r * math.sin(a)))
    nc = U['neck_top'] - nw                         # neck: straight sides, half-circle top
    for i in range(0, 2 * k + 1):
        a = math.radians(0 + 180 * i / (2 * k))
        pts.append((nw * math.cos(a), nc + nw * math.sin(a)))
    for i in range(1, k):
        a = math.radians(0 - 90 * i / k)
        pts.append((-nw - r + r * math.cos(a), sh + r + r * math.sin(a)))
    for i in range(k + 1):
        a = math.radians(90 + 90 * i / k)
        pts.append((-hw + r + r * math.cos(a), sh - r + r * math.sin(a)))
    out = []
    for p in pts:
        if not out or (abs(out[-1][0] - p[0]) > 1e-6 or abs(out[-1][1] - p[1]) > 1e-6):
            out.append(p)
    return out


def rounded_rect(x0, h0, x1, h1, r, k=6):
    pts = []
    for cx, ch, a0 in ((x1 - r, h0 + r, -90), (x1 - r, h1 - r, 0), (x0 + r, h1 - r, 90), (x0 + r, h0 + r, 180)):
        for i in range(k + 1):
            a = math.radians(a0 + 90 * i / k)
            pts.append((cx + r * math.cos(a), ch + r * math.sin(a)))
    return pts


# ------------------------------------------------------------------------------------------- instruments
# id: x, h, face radius r, rim style, face region (gauge atlas), on the upper section?, movers [(suffix, kind)], zero_deg
# zero_deg: where the face puts the scale's first value (clockwise from 12 o'clock as seen by the pilot); the needle mesh is
# built pointing there, so the plugin's 'deg from rest' maps straight onto the painted scale.
DIALS = {
    'turn':  dict(x=0.000, h=0.405, r=0.040, rim='black', face='turn', upper=True, movers=[('needle', 'needle'), ('slip', 'ball')], zero=0),
    'asi':   dict(x=-0.062, h=0.290, r=0.040, rim='white', face='asi', upper=True, movers=[('needle', 'needle')], zero=0),
    'alt':   dict(x=0.066, h=0.290, r=0.046, rim='black', face='alt', upper=True, movers=[('needle', 'needle'), ('needle_short', 'short')], zero=0),
    'rpm':   dict(x=-0.125, h=0.105, r=0.045, rim='black', face='rpm', movers=[('needle', 'needle')], zero=-150),
    'boost': dict(x=0.275, h=0.105, r=0.037, rim='chrome', face='boost', movers=[('needle', 'needle')], zero=-135, plate=0.098),
    'oilp':  dict(x=0.104, h=0.163, r=0.026, rim='yellow', face='oilp', movers=[('needle', 'needle')], zero=-135),
    'oilt':  dict(x=0.170, h=0.163, r=0.026, rim='yellow', face='oilt', movers=[('needle', 'needle')], zero=-135),
    'water': dict(x=0.140, h=0.088, r=0.024, rim='black', face='water', movers=[('needle', 'needle')], zero=-135),
    'fuel':  dict(x=0.338, h=0.188, r=0.027, rim='blue', face='fuel', movers=[('needle', 'needle')], zero=-135),
    'clock': dict(x=-0.335, h=0.185, r=0.026, rim='chrome', face='clock', movers=[], zero=0),
    'fuelp': dict(x=-0.333, h=0.078, r=0.022, rim='black', face='fuelp', movers=[], zero=-135),
}
# value scales (deg per unit from zero_deg); the plugin holds the same constants (nimrod_stub_test cross-checks them)
SCALES = {
    'asi': dict(value='indicated airspeed', unit='kt', v0=0, v1=260, sweep=330),
    'alt': dict(value='altitude, long needle', unit='ft', v0=0, v1=1000, sweep=360),
    'alt_short': dict(value='altitude, short needle', unit='ft', v0=0, v1=10000, sweep=360),
    'rpm': dict(value='engine rpm', unit='rpm', v0=0, v1=3000, sweep=300),
    'boost': dict(value='boost', unit='lb/in2', v0=-4, v1=8, sweep=270),
    'oilp': dict(value='oil pressure', unit='psi', v0=0, v1=100, sweep=270),
    'oilt': dict(value='oil temperature', unit='C', v0=0, v1=100, sweep=270),
    'water': dict(value='coolant temperature', unit='C', v0=0, v1=140, sweep=270),
    'fuel': dict(value='fuel contents', unit='%', v0=0, v1=100, sweep=270),
    'turn': dict(value='rate of turn', unit='deg/s', v0=0, v1=3, sweep=30),
    'slip': dict(value='sideslip ball', unit='deg', v0=0, v1=1, sweep=3),
    'compass': dict(value='magnetic heading (card)', unit='deg', v0=0, v1=360, sweep=-360),
}
TAC = dict(x=0.0, h=0.112, w=0.122, hgt=0.070)            # compact retrofit tac screen (mfd_center) on the lower panel centre
COMPASS = dict(x=0.0, y=-0.405, z=0.020, r=0.058, hgt=0.066)   # compass bowl under the lower panel (card = gauge_compass_card)

# other panel furniture (x, h, ...)
MAGNETO = dict(x=-0.255, h=0.185, w=0.070, hgt=0.042, d=0.026)
COCKS = [(-0.186, 0.198), (0.238, 0.200)]                  # brass fuel cocks on the lower panel (T-handles)
DATAPLATE = dict(x=-0.090, h=0.168, w=0.082, hgt=0.040)
CARDHOLDER = dict(x=0.030, h=0.172, w=0.046, hgt=0.046)    # small square frame (photo 50 centre)
TOGGLES = [(-0.245, 0.088), (-0.214, 0.088)]
SERIAL_PLATE = dict(x=0.0, h=0.333, w=0.040, hgt=0.016)   # label between the two big dials (upper section)
LOWER_CARDS = [dict(id='devcard', x=-0.240, h=0.030, w=0.066, hgt=0.034), dict(id='ratecard', x=0.355, h=0.035, w=0.044, hgt=0.032)]

# painted labels on the lower panel / upper section faces: (text, x, h, size m)
LABELS_LOWER = [('R.P.M.', -0.125, 0.044, 0.0075), ('OIL PRESS', 0.104, 0.126, 0.0050), ('OIL TEMP', 0.170, 0.126, 0.0050),
                ('RAD. TEMP', 0.140, 0.052, 0.0050), ('FUEL', 0.338, 0.148, 0.0060), ('BOOST', 0.275, 0.044, 0.0060),
                ('MAGNETOS', -0.255, 0.152, 0.0050), ('ON', -0.222, 0.198, 0.0050), ('OFF', -0.148, 0.198, 0.0050),
                ('ON', 0.202, 0.200, 0.0050), ('OFF', 0.276, 0.200, 0.0050), ('MAIN', -0.186, 0.168, 0.0045), ('GRAVITY', 0.238, 0.170, 0.0045),
                ('NAV', -0.245, 0.116, 0.0045), ('PANEL', -0.212, 0.116, 0.0045), ('FUEL PRESS', -0.333, 0.046, 0.0045),
                ('TAC', 0.0, 0.054, 0.0045), ('CLOCK', -0.335, 0.150, 0.0045)]
LABELS_UPPER = [('TURN', 0.0, 0.456, 0.0050)]

# ------------------------------------------------------------------------------------------- textures
GAUGE_N = 2048
GAUGE_GRID = 8                      # 256 px cells; big dials span 2 x 2
# region: (col, row, span) - row 0 at the bottom (v 0)
GAUGE_CELLS = {
    'turn': (0, 0, 2), 'asi': (2, 0, 2), 'alt': (4, 0, 2), 'rpm': (6, 0, 2),
    'boost': (0, 2, 1), 'oilp': (1, 2, 1), 'oilt': (2, 2, 1), 'water': (3, 2, 1), 'fuel': (4, 2, 1), 'clock': (5, 2, 1),
    'fuelp': (6, 2, 1), 'compass': (0, 4, 2), 'oxygen': (7, 2, 1),
    'needle': (0, 3, 1), 'needle_dark': (1, 3, 1), 'ball': (2, 3, 1), 'hub': (3, 3, 1),
    'rim_black': (4, 3, 1), 'rim_yellow': (5, 3, 1), 'rim_blue': (6, 3, 1), 'rim_white': (7, 3, 1), 'rim_chrome': (2, 4, 1),
    'glass_dark': (3, 4, 1), 'counter': (4, 4, 2),
}


def gauge_uv(region, lu, lv):
    """UV of a point in a gauge region; lu, lv in -1..1 (disc radius 0.96 of the half cell)."""
    c, r, s = GAUGE_CELLS[region]
    g = GAUGE_GRID
    h = 0.5 * s / g * 0.96
    return ((c + s / 2) / g + lu * h, (r + s / 2) / g + lv * h)


CKART_N = 2048
# region: (px0, py0, px1, py1) in image pixels (py from the top); panel regions map panel coordinates linearly
CKART = {
    'lower': (0, 0, 2048, 640),                 # lower panel face: x -0.385..0.385, h 0..0.235
    'upper': (0, 648, 640, 1336),               # raised section face: x -0.123..0.123, h 0.200..0.462
    'seat': (648, 648, 1672, 1336),             # bucket seat skin, unrolled: u = section arc (side, pan/back, side), v = pan front -> back top
    'dataplate': (1680, 648, 2048, 832),
    'devcard': (1680, 840, 2048, 1024),
    'ratecard': (1680, 1032, 2048, 1216),
    'wallcard1': (1680, 1224, 2048, 1408),
    'wallcard2': (0, 1344, 368, 1528),
    'trimcard': (376, 1344, 744, 1528),
    'quadrant': (752, 1344, 1264, 1472),        # quadrant top plate with engraved scale
    'ammo': (1272, 1344, 1656, 1600),           # gun-firing / ammo counter box face
    'magneto': (1664, 1416, 2048, 1600),
    'serial': (0, 1536, 368, 1648),
    'cockplate': (376, 1536, 744, 1720),
    'oxyface': (752, 1480, 1264, 1736),
    'stencil': (1272, 1608, 2048, 1800),        # seat-back / wall stencil
    'breech': (0, 1808, 168, 2048),            # Vickers casing rear face: rear plate, crank boss, stamping
}
PANEL_REGION = {'lower': (LOWER['x0'], LOWER['x1'], LOWER['h0'], LOWER['h1']),
                'upper': (-UPPER['half_w'], UPPER['half_w'], UPPER['h0'], UPPER['neck_top'])}


def ckart_uv(region, fu, fv):
    """UV for a fraction (fu right, fv up) inside a ck_art region."""
    x0, y0, x1, y1 = CKART[region]
    N = CKART_N
    return ((x0 + fu * (x1 - x0)) / N, 1.0 - (y1 - fv * (y1 - y0)) / N)


def panel_uv(region, x, h):
    a, b, c, d = PANEL_REGION[region]
    return ckart_uv(region, (x - a) / (b - a), (h - c) / (d - c))


PLACARDS = {
    'dataplate': ['HAWKER NIMROD I', 'No. S1577', 'ROLLS-ROYCE KESTREL', 'V.S. 6/4/1932'],
    'devcard': ['COMPASS', 'DEVIATION', 'N 0  E +1', 'S -1  W 0'],
    'ratecard': ['RATE', 'ONE', '3 DEG/SEC'],
    'wallcard1': ['FUEL SYSTEM', 'MAIN 50 GAL', 'GRAVITY 12 GAL', 'USE MAIN FOR', 'TAKE-OFF'],
    'wallcard2': ['ENGINE LIMITS', 'MAX RPM 2900', 'CLIMB 2600', 'OIL 80 C MAX', 'RAD 120 C MAX'],
    'trimcard': ['TAIL', 'NOSE DOWN', '^', 'NOSE UP'],
    'serial': ['S1577'],
    'cockplate': ['PRIMING', 'PUMP'],
    'stencil': ['NOT TO BE USED AS A STEP'],
}

# tiling materials of the cockpit (detail UV = 2 m per unit; Unity / Blender scale it by these factors)
TILE_SCALE = {'ck_paint': 4.0, 'ck_crinkle': 8.0, 'ck_brass': 8.0, 'ck_leather': 6.0, 'ck_wood': 4.0, 'ck_floor': 4.0,
              'ck_alu': 4.0, 'ck_tube': 8.0, 'ck_canvas': 10.0, 'ck_red': 6.0, 'ck_lining': 4.0, 'ck_rubber': 8.0}
# Unity / Blender PBR per tile material: (metallic, smoothness)
TILE_PBR = {'ck_paint': (0.15, 0.40), 'ck_crinkle': (0.10, 0.30), 'ck_brass': (0.90, 0.62), 'ck_leather': (0.0, 0.45), 'ck_wood': (0.0, 0.55),
            'ck_floor': (0.0, 0.20), 'ck_alu': (0.85, 0.55), 'ck_tube': (0.35, 0.40), 'ck_canvas': (0.0, 0.10), 'ck_red': (0.05, 0.50),
            'ck_lining': (0.0, 0.15), 'ck_rubber': (0.0, 0.25)}
