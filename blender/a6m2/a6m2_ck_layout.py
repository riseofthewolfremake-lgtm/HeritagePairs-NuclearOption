"""A6M2 Zero cockpit (round 4): shared layout table, pure Python (no bpy / mathutils).

Used by blender/a6m2/a6m2_cockpit.py (geometry, UVs), blender/a6m2/textures/make_cockpit_art_a6m2.py (PIL dial atlas) and the
plugin mirror tools/stub_tests_a6m2_r4.py, so painted scales, needles and the plugin's value -> angle maps stay in one place.

Layout: WT cockpit extract as a VISUAL reference only (design 8: eye (+0.032, -1.025, 0.79); main panel needles y -0.30..-0.275,
x -0.25..+0.25, z 0.28-0.40; sub-panel between the breeches z 0.47-0.58; Type 98 sight glass x +0.007..+0.057, z 0.749-0.804,
y -0.376..-0.330; breeches x +-0.206 (our gun line), rear ends 0.64 m ahead of the eye). Pre-scale metres, Blender frame
(x right, y forward, z up); a6m2_cockpit applies K / the span plug like every other generator.

Movers (A6M2 branch of B25H.Instruments, A6M2Cockpit.cs): gauge_<id>_needle (/ _needle_short / gauge_turn_slip / gauge_horizon_card /
gauge_compass_card). Local +X (Unity) toward the pilot (compass card: +X up); rest pose = the scale's first value (the needle mesh
points at the face's zero mark); + angle = clockwise as seen by the pilot (the B-25H / Nimrod convention, verified in game).
"""
import math

# r8 (user review 1: "all wrong" against the WT cockpit): every number below is MEASURED on the WT cockpit model (ortho renders with a
# metric grid, study/a6m2/r8/ortho_wt_ng/*_grid.png; objects list study/a6m2/r8/measure/ckpt_objects.json) and CENTRED (the WT
# cockpit sits 32 mm right of the centreline with its headPos; the real seat, sight and stick are on the centreline, user order).
PANEL_Y = -0.300           # main panel face (WT needles y -0.297..-0.275)
PANEL_Z0, PANEL_Z1 = 0.262, 0.466
PANEL_HALF = 0.297         # WT main plate x -0.297..+0.297
LOWER = dict(x0=-0.215, x1=0.255, z0=0.175, z1=0.262, y=-0.312)      # WT lower plates (clock / lamp / oil-cooler shutter), 10 mm recessed
SUB_Y = -0.290             # sub-panel between the breeches (WT aviahorizon face y -0.288)
SUB_Z0, SUB_Z1, SUB_HALF = 0.466, 0.600, 0.075     # r8b: raised housing 1.2-1.3x the r8 one (critique), bezel frame added in the generator
COAMING = dict(y_lip=-0.275, y_front=-0.200, z_apex=0.700, z_foot=0.440, t=0.010)   # arch over panel + breeches (WT green hood); r8c: rim at y -0.275 (WT side ortho) so the receivers stand out behind it
BULKHEAD_Y = -0.240        # closed firewall / tub front (r8: the r7 panel left gaps into the engine bay)

# id: panel ('main' / 'sub' / 'lower'), x, z (dial centre), face radius r, rim, movers [(suffix, kind)], zero_deg
# WT positions (needle pivots / bezels, ortho panel_cut): rows z 0.377 / 0.311, columns |x| 0.103 / 0.176 / 0.246; sub-panel +-0.038, z 0.534
DIALS = {
    'horizon': dict(panel='sub', x=-0.038, z=0.533, r=0.031, rim='black', movers=[('card', 'card')], zero=0),
    'turn':    dict(panel='sub', x=0.038, z=0.533, r=0.031, rim='black', movers=[('needle', 'needle'), ('slip', 'ball')], zero=0),
    'fuelp':   dict(panel='main', x=-0.247, z=0.377, r=0.027, rim='black', movers=[], zero=-135),
    'clock':   dict(panel='main', x=-0.175, z=0.377, r=0.021, rim='black', movers=[], zero=0),
    'asi':     dict(panel='main', x=-0.103, z=0.377, r=0.026, rim='black', movers=[('needle', 'needle')], zero=-165),
    'vsi':     dict(panel='main', x=0.103, z=0.377, r=0.026, rim='black', movers=[('needle', 'needle')], zero=-90),
    'oilp':    dict(panel='main', x=0.178, z=0.377, r=0.020, rim='black', movers=[('needle', 'needle')], zero=-135),
    'rpm':     dict(panel='main', x=0.246, z=0.377, r=0.027, rim='black', movers=[('needle', 'needle')], zero=-150),
    'exht':    dict(panel='main', x=-0.247, z=0.311, r=0.027, rim='black', movers=[], zero=-135),
    'fuel':    dict(panel='main', x=-0.175, z=0.311, r=0.020, rim='black', movers=[('needle', 'needle')], zero=-135),
    'alt':     dict(panel='main', x=-0.103, z=0.311, r=0.026, rim='black', movers=[('needle', 'needle'), ('needle_short', 'short')], zero=0),
    'boost':   dict(panel='main', x=0.103, z=0.311, r=0.026, rim='black', movers=[('needle', 'needle')], zero=-135),
    'oilt':    dict(panel='main', x=0.178, z=0.311, r=0.020, rim='black', movers=[('needle', 'needle')], zero=-135),
    'cht':     dict(panel='main', x=0.245, z=0.311, r=0.027, rim='black', movers=[], zero=-135),
    'oxy':     dict(panel='lower', x=-0.098, z=0.214, r=0.021, rim='black', movers=[], zero=-135),
}
# compass: the WT boxed centre instrument spans both rows (x +-0.049, z 0.297..0.395); our drum card in its window
COMPASS = dict(x=0.000, z=0.346, w=0.070, h=0.040, r=0.032, box_w=0.097, box_h=0.098)
PLACARD = dict(x=0.040, z=0.205, w=0.070, h=0.040)        # data box on the lower plate

# breeches (WT jp_navy_7_7_mm_type97 in the cockpit: x +-0.241 outer, rear end y -0.380, z 0.474..0.730); receiver centre |x| 0.188
BREECH = dict(x=0.185, y_rear=-0.355, y_front=-0.080, z_bot=0.480, z_top=0.645, w=0.058, knob_x=0.105, knob_y=-0.290, knob_z=0.710)   # r8c: WT ortho (br_ortho): slim receiver 58 x 165 mm, knob 32 x 40 x 50 mm
# Type 98 sight on the centreline: body under the line of sight (top z 0.745, 45 mm under the eye), transparent tinted glass + emissive
# reticle. r8m (user review r8l: the glass frame floated over the sight): bottom edge y -0.330 z 0.761 forward, top y -0.366 z 0.804 aft
# (WT collimator.ckpt verts), hinged on the sight head (head plate top head_z, hinge pin axis hinge_y / hinge_z)
SIGHT = dict(y0=-0.300, y1=-0.420, body_top=0.745, body_bot=0.614, half=0.034, gy0=-0.330, gy1=-0.366, gz0=0.761, gz1=0.804, ghalf=0.026,
             head_z=0.743, hinge_y=-0.330, hinge_z=0.758)
# left console (WT throttle / mixture / prop pitch / trimmer / switch box), right console (gear selector aft, radio box fwd)
THROTTLE = dict(x=-0.292, y=-0.730, z=0.360, grip=(-0.215, -0.660, 0.478))
# r8m (user review r8l: full throttle clipped the mixture / pitch levers): sector plate concentric with the throttle pivot (fan 22..78 deg
# from vertical, plate tp.x + plate_dx, radius arc_r, slot strip at slot_r), mixture / prop-pitch / supercharger levers in one plane x = xm
# outboard of the plate (WT has them outboard of / around the throttle travel)
QUAD = dict(plate_dx=-0.022, arc_r=0.108, slot_r=0.090, a0=22, a1=78, xm=-0.334)
TRIM = dict(x=-0.300, y=-0.874, z=0.307, r=0.072)
STICK = dict(y_pivot=-0.500, y_top=-0.515, z_top=0.240)        # grip end z 0.36 (WT stick_ailerons top z 0.356); r8m: near-vertical so full push (Joystick 14 deg) clears the panel by 22 mm
SEAT = dict(y_front=-0.835, y_back=-1.275, z=-0.010, w=0.400)
WALL_FRAMES_Y = (-0.560, -0.790, -1.100)
RAIL_PLATES_Y = (-0.575, -0.950)          # r8b: drilled plates under the sill rail (WT right wall -0.55..-0.58, -0.92..-1.0; left -0.79, -1.10)
LOWER_PLATES = [(-0.215, -0.132, 0.180, 0.262), (-0.128, 0.020, 0.150, 0.262), (0.126, 0.252, 0.180, 0.262)]   # WT lower pedestal pieces
RING_SIGHT = dict(x=-0.068, y=-0.250, z=0.805, r=0.024, post_z=0.700)   # WT ring-and-bead sight left of the reflector

# value -> needle angle (deg clockwise from the zero mark); mirrored in A6M2Math (A6M2Cockpit.cs) and the stub test
SCALES = {
    'asi':    dict(v0=0.0, v1=350.0, sweep=330.0, unit='kt'),         # 0-350 kt over 330 deg
    'alt':    dict(v0=0.0, v1=1000.0, sweep=360.0, unit='m'),         # long hand 1,000 m a turn
    'alt_short': dict(v0=0.0, v1=10000.0, sweep=360.0, unit='m'),   # short hand 10,000 m a turn
    'vsi':    dict(v0=-20.0, v1=20.0, sweep=300.0, unit='m/s'),          # see vsi_deg: 0 m/s at the rest mark (9 o'clock), +-150 deg
    'rpm':    dict(v0=0.0, v1=3500.0, sweep=300.0, unit='rpm'),
    'boost':  dict(v0=-400.0, v1=200.0, sweep=270.0, unit='mmHg'),
    'oilp':   dict(v0=0.0, v1=10.0, sweep=270.0, unit='kg/cm2'),
    'oilt':   dict(v0=0.0, v1=120.0, sweep=270.0, unit='C'),
    'fuel':   dict(v0=0.0, v1=100.0, sweep=270.0, unit='%'),
    'turn':   dict(deg_per_dps=10.0, max=45.0),
    'slip':   dict(deg_per_deg=1.5, max=28.0),
    'horizon': dict(pitch_m_per_deg=-0.0006, pitch_max=25.0),
}
RATED_RPM = 2550.0          # Sakae 12 at prop rpm ratio 1 (governed)


def lin_deg(key, v):
    s = SCALES[key]
    t = (min(max(v, s['v0']), s['v1']) - s['v0']) / (s['v1'] - s['v0'])
    return t * s['sweep']


def vsi_deg(vs):
    """VSI: needle rest (zero_deg -90 = 9 o'clock) = 0 m/s; climb clockwise, sink anticlockwise, +-150 deg at +-20 m/s."""
    return max(-20.0, min(20.0, vs)) * 7.5


# ------------------------------------------------------------------ gauge atlas (2048 px, 8 x 8 cells of 256 px; big faces span 2 x 2)
GAUGE_N, GAUGE_GRID = 2048, 8
GAUGE_CELLS = {   # region: (col, row, span), row 0 at the bottom (v 0)
    'asi': (0, 0, 2), 'alt': (2, 0, 2), 'rpm': (4, 0, 2), 'horizon': (6, 0, 2),
    'turn': (0, 2, 2), 'boost': (2, 2, 2), 'vsi': (4, 2, 2), 'horizon_card': (6, 2, 2),
    'oilp': (0, 4, 1), 'oilt': (1, 4, 1), 'fuel': (2, 4, 1), 'clock': (3, 4, 1),
    'needle': (4, 4, 1), 'needle_short': (5, 4, 1), 'ball': (6, 4, 1), 'hub': (7, 4, 1),
    'rim_black': (0, 5, 1), 'rim_alu': (1, 5, 1), 'glass_dark': (2, 5, 1), 'black': (3, 5, 1),
    'compass_card': (0, 6, 4), 'compass_window': (4, 6, 1), 'label': (5, 6, 1), 'reticle': (6, 6, 2),
    'fuelp': (4, 5, 1), 'cht': (5, 5, 1), 'oxy': (6, 5, 1), 'exht': (7, 5, 1),
    'placard': (0, 7, 1), 'switchplate': (1, 7, 1), 'red': (2, 7, 1), 'cream': (3, 7, 1),
}


def gauge_uv(region, lu, lv):
    """UV of a point in a gauge region; lu, lv in -1..1 (disc radius 0.96 of the half cell)."""
    c, r, s = GAUGE_CELLS[region]
    g = GAUGE_GRID
    h = 0.5 * s / g * 0.96
    return ((c + s / 2) / g + lu * h, (r + s / 2) / g + lv * h)


def strip_uv(region, u, v):
    """UV in a rectangular region, u / v 0..1 over the whole cell span (compass drum card strip)."""
    c, r, s = GAUGE_CELLS[region]
    g = GAUGE_GRID
    return ((c + u * s) / g, (r + v * (s if region != 'compass_card' else 1)) / g)
