"""B-25H 1.8.4 dials (offline C, 2026-11-08): every dial of the main panel moves.

In game 1.8.2 (study/ingame_182 P9) the compass, clock, suction, ammeter, carburettor / free-air temperature and de-icer pressure dials
never moved: they are painted into the fal panel art (b25h_cockpit_layout.DECO). The six small engine / system dials (oil press, oil temp,
cyl temp, hydraulic, flaps, gear) were real dial faces with a BAKED needle and no mover (b25h_v3_cockpit.GAUGES movers []).

1.8.4: each painted dial gets a real dial on top of it (bezel ring + needle-free procedural face + needle / card mover, the same style as
the REAL dials), and the six small dials get needle-free faces + a needle. The B25H.Instruments plugin (Dials184.cs) drives every mover by
name. Pure Python (no bpy): imported by b25h_cockpit2.py (geometry + contract info) and textures/make_gauges.py (faces).

SCALES must equal Plugin.B25HScales in src/B25H.Instruments/Dials184.cs (tools/dials184_stub_test.py compares them).
"""
# id -> (v0, v1, a0 deg at v0 clockwise from 12 o'clock, sweep deg)
SCALES = {
    'oil_press': (0, 200, -135, 270), 'oil_temp': (-50, 150, -135, 270), 'cyl_temp': (0, 350, -135, 270), 'hydraulic': (0, 2000, -135, 270),
    'flaps_pos': (0, 1, -90, 180), 'gear_pos': (0, 1, -90, 180),
    'suction': (0, 10, -135, 270), 'ammeter': (0, 150, -135, 270), 'brake_press': (0, 1500, -135, 270), 'volts': (0, 30, -135, 270),
    'carb_temp': (-50, 50, -135, 270), 'free_air': (-50, 50, -135, 270), 'deicer': (0, 20, -135, 270), 'oxygen': (0, 500, -135, 270),
}
VALUES = {   # what the plugin feeds (contract info / documentation)
    'oil_press': 'oil pressure psi, mean of the props: 40 at idle ratio 0 .. 82 at governed rpm, 0 engines stopped',
    'oil_temp': 'oil temperature C, lag 60 s to 55 + 25 sqrt(powerRatio), free-air when stopped',
    'cyl_temp': 'cylinder-head temperature C, lag 50 s to 120 + 110 sqrt(powerRatio)',
    'hydraulic': 'hydraulic pressure psi: 1050 engines running, 800 while the gear moves, lag 3 s',
    'flaps_pos': 'flap position 0 up .. 1 down (max HighLiftDevice.position of the real flap devices)',
    'gear_pos': 'gear position 0 up .. 1 down (gear state, 6 s travel)',
    'suction': 'vacuum inHg: 4.8 x clamp01(prop rpm ratio / 0.6)',
    'ammeter': 'generator load A: 30 + 25 sqrt(powerRatio) + ripple, 0 engines stopped',
    'brake_press': 'brake accumulator psi: 1000 - 300 x brake input with engines running',
    'volts': 'bus volts: 28.2 - 0.01 x A running, 24 battery',
    'carb_temp': 'carburettor air C: free-air + 12 + 18 sqrt(powerRatio), lag 20 s',
    'free_air': 'free-air C: ISA(altitude) + 0.9 v^2 / 2010 (no air-temperature model in the game)',
    'deicer': 'de-icer pressure psi: 8 x clamp01(rpm ratio / 0.6) with engines running',
    'oxygen': 'oxygen psi: 425, -1 psi/min above 3,000 m',
}
# face cells (b25h_gauges atlas): the six small dials keep 12-17 (redrawn needle-free), the new faces use 18-26; the compass reuses the
# heading bezel (3) + compass card (11)
FACE = {'oil_press': 12, 'oil_temp': 13, 'cyl_temp': 14, 'hydraulic': 15, 'flaps_pos': 16, 'gear_pos': 17,
        'clock': 18, 'suction': 19, 'ammeter': 20, 'carb_temp': 21, 'free_air': 22, 'deicer': 23, 'oxygen': 24, 'brake_press': 25, 'volts': 26}
NEW_CELLS = [18, 19, 20, 21, 22, 23, 24, 25, 26]
# movers of the six small REAL dials (b25h_v3_cockpit.GAUGES had [])
SMALL_MOVERS = {k: [('needle', 'needle', 62)] for k in ('oil_press', 'oil_temp', 'cyl_temp', 'hydraulic', 'flaps_pos', 'gear_pos')}
# painted dials covered by real ones: (gauge id, scale id, x, z, r) at the DECO positions (+ the right de-icer, measured on the art:
# source px (2937, 696) -> x 0.567, z 0.695), movers
OVER = [
    ('clock', 'clock', -0.575, 0.770, 0.025, [('needle', 'needle', 62), ('needle_short', 'short', 63)]),
    ('suction_L', 'suction', -0.575, 0.690, 0.024, [('needle', 'needle', 62)]),
    ('suction_C', 'suction', -0.115, 0.800, 0.022, [('needle', 'needle', 62)]),
    ('ammeter', 'ammeter', -0.020, 0.800, 0.022, [('needle', 'needle', 62)]),
    ('brake_press', 'brake_press', -0.115, 0.880, 0.020, [('needle', 'needle', 62)]),
    ('volts', 'volts', -0.020, 0.880, 0.020, [('needle', 'needle', 62)]),
    ('carb_temp_L', 'carb_temp', -0.430, 0.620, 0.022, [('needle', 'needle', 62)]),
    ('free_air_L', 'free_air', -0.300, 0.620, 0.022, [('needle', 'needle', 62)]),
    ('compass', 'compass', 0.155, 0.635, 0.024, [('card', 'card', 11)]),
    ('deicer_L', 'deicer', 0.275, 0.635, 0.022, [('needle', 'needle', 62)]),
    ('carb_temp_R', 'carb_temp', 0.480, 0.810, 0.026, [('needle', 'needle', 62)]),
    ('free_air_R', 'free_air', 0.480, 0.735, 0.026, [('needle', 'needle', 62)]),
    ('oxygen', 'oxygen', 0.565, 0.775, 0.022, [('needle', 'needle', 62)]),
    ('deicer_R', 'deicer', 0.567, 0.695, 0.022, [('needle', 'needle', 62)]),
]


def face_cell(scale_id):
    return 3 if scale_id == 'compass' else FACE[scale_id]


def info_for(scale_id):
    if scale_id in SCALES:
        v0, v1, a0, sw = SCALES[scale_id]
        return dict(value=VALUES[scale_id], v0=v0, v1=v1, a0=a0, sweep=sw, angle='a0 + clamp01((v - v0) / (v1 - v0)) * sweep',
                    driver='B25H.Instruments 1.8.4 Dials184.cs')
    if scale_id == 'clock':
        return dict(value='game time of day (LevelInfo.timeOfDay): long = minutes (360 deg / h), short = hours (30 deg / h)', driver='B25H.Instruments 1.8.4')
    if scale_id == 'compass':
        return dict(value='standby magnetic compass: card angle = -heading, lag 1.5 s', driver='B25H.Instruments 1.8.4')
    return {}


def plugin_names():
    """every mover name the plugin binds (Dials184.cs B25HExtraNames)."""
    out = [f'gauge_{k}_needle' for k in SMALL_MOVERS]
    for gid, sid, x, z, r, mv in OVER:
        for suf, kind, cell in mv:
            out.append(f'gauge_{gid}_{suf}' if gid != 'compass' else 'gauge_compass_card')
    return out
