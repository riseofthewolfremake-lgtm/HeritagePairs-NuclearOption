"""Design numbers for the B-25H v2 model (Blender space: nose +Y, up +Z, right wing +X, metres).

Sources / derivation (see report): published B-25H data (span 20.60 m, length 15.54 m, height
4.98 m, prop 3.86 m dia, 47 in main tyres) plus proportions MEASURED (bounding boxes and
cross-section slices only) from the user's B-25J reference, scaled by K = 20.60/20.98 and mirrored
into our axes (y_ours = -K * y_ref, x_ours = -K * x_ref). No reference mesh data is used.
"""
import math

K = 20.60 / 20.98

# ---------------------------------------------------------------- fuselage
NOSE_TIP_Y = 5.94          # H solid nose tip (body length nose->tail glazing ~15.66 m)
NOSE_BASE_Y = 4.55         # windscreen base / nose-cockpit split
NOSE_TIP_Z = 0.08
TAIL_END_Y = -9.72
SKIN_T = 0.02              # visual skin thickness

# split planes (front -> back)
SPLITS = {'fus_nose': (NOSE_TIP_Y, 4.55), 'fus_cockpit': (4.55, 2.62), 'fus_forward': (2.62, 1.30),
          'fus_center': (1.30, -1.80), 'fus_rear': (-1.80, -6.10), 'fus_tail': (-6.10, TAIL_END_Y)}

# (y, half width, z bottom, z top, top-corner radius factor * hw)
FUS_TABLE = [
    (4.55, 0.720, -0.850, 0.970, 0.62),
    (4.42, 0.722, -0.853, 1.100, 0.64),
    (4.30, 0.724, -0.856, 1.210, 0.66),
    (4.15, 0.725, -0.860, 1.300, 0.667),
    (3.95, 0.725, -0.862, 1.345, 0.667),
    (3.75, 0.725, -0.866, 1.360, 0.667),
    (3.30, 0.725, -0.875, 1.360, 0.667),
    (2.00, 0.725, -0.880, 1.360, 0.667),
    (1.20, 0.720, -0.880, 1.355, 0.667),
    (-1.00, 0.720, -0.880, 1.340, 0.667),
    (-1.77, 0.715, -0.870, 1.320, 0.667),
    (-2.16, 0.715, -0.860, 1.300, 0.667),
    (-2.55, 0.715, -0.840, 1.280, 0.667),
    (-2.95, 0.710, -0.820, 1.260, 0.667),
    (-3.34, 0.700, -0.800, 1.240, 0.667),
    (-3.73, 0.685, -0.770, 1.210, 0.667),
    (-4.12, 0.655, -0.750, 1.190, 0.667),
    (-4.52, 0.625, -0.700, 1.160, 0.667),
    (-4.91, 0.600, -0.650, 1.140, 0.667),
    (-5.30, 0.580, -0.600, 1.110, 0.667),
    (-5.70, 0.560, -0.550, 1.080, 0.667),
    (-6.09, 0.540, -0.500, 1.060, 0.667),
    (-6.48, 0.530, -0.450, 1.030, 0.667),
    (-6.87, 0.510, -0.400, 1.000, 0.680),
    (-7.27, 0.490, -0.360, 0.990, 0.700),
    (-7.66, 0.470, -0.320, 1.080, 0.760),
    (-8.05, 0.450, -0.260, 1.190, 0.800),
    (-8.45, 0.440, -0.180, 1.300, 0.830),
    (-8.84, 0.420, -0.110, 1.365, 0.850),
    (-9.23, 0.400, -0.060, 1.300, 0.850),
    (-9.45, 0.370, -0.010, 1.180, 0.850),
    (-9.62, 0.330, 0.030, 0.950, 0.850),
    (-9.72, 0.280, 0.100, 0.720, 0.850),
]
RB_FACTOR = 0.42           # bottom corner radius = 0.42 * hw

# openings
CANOPY_Y = (2.75, 4.55)
NOSE_WELL_Y = (1.80, 3.95)
NOSE_WELL_HALF_X = 0.29
BAY_Y = (-1.45, 1.20)
BAY_HALF_X = 0.60
WAIST_L_Y = (-3.40, -2.85)
WAIST_R_Y = (-3.95, -3.40)
WAIST_Z = (-0.10, 0.60)
TAIL_GLASS_Y = -8.05

# ---------------------------------------------------------------- wing
WING_ROOT_X = 0.62
WING_LE = lambda ax: 1.32 - 0.0785 * (ax - 0.79)
WING_TE = lambda ax: -2.39 + 0.133 * (ax - 0.79)
WING_TIP = [(9.58, 0.630, -1.220), (9.82, 0.500, -1.100), (10.00, 0.360, -0.980), (10.12, 0.220, -0.860),
            (10.22, 0.060, -0.680), (10.28, -0.090, -0.460), (10.30, -0.180, -0.300)]
WING_BREAK_X = 2.95        # inner/outer split and dihedral break (nacelle centreline)
WING_TIPSPLIT_X = 6.15     # outer/tip split = aileron root
DIHEDRAL_IN = math.radians(4.0)
DIHEDRAL_OUT = math.radians(0.5)
WING_ROOT_Z = 0.33
HINGE_F = 0.74             # flap/aileron hinge at 74 % chord (measured 72-76 %)
FLAP_IN_X = (0.74, 2.41)
FLAP_OUT_X = (3.40, 6.15)
AILERON_X = (6.15, 9.58)

# ---------------------------------------------------------------- nacelle / engine / prop
NAC_X = 2.95
NAC_Z = 0.0
FIREWALL_Y = 1.62
COWL_REAR_Y = 1.80
COWL_FRONT_Y = 2.72
PROP_Y = 2.98
PROP_R = 3.86 / 2
NAC_TABLE = [  # y, half width, z bottom, z top, superellipse n
    (1.62, 0.765, -0.765, 0.765, 2.0),
    (1.40, 0.765, -0.770, 0.800, 2.1),
    (1.10, 0.760, -0.770, 0.860, 2.2),
    (0.80, 0.755, -0.770, 0.890, 2.3),
    (0.50, 0.750, -0.770, 0.890, 2.3),
    (0.25, 0.750, -0.770, 0.870, 2.3),
    (0.00, 0.745, -0.770, 0.850, 2.3),
    (-0.40, 0.730, -0.765, 0.800, 2.3),
    (-0.80, 0.700, -0.760, 0.740, 2.3),
    (-1.20, 0.655, -0.750, 0.680, 2.3),
    (-1.60, 0.600, -0.720, 0.610, 2.3),
    (-2.00, 0.520, -0.670, 0.530, 2.2),
    (-2.25, 0.450, -0.620, 0.480, 2.2),
    (-2.50, 0.370, -0.550, 0.420, 2.1),
    (-2.75, 0.270, -0.460, 0.340, 2.0),
    (-2.95, 0.170, -0.360, 0.250, 2.0),
    (-3.08, 0.090, -0.280, 0.180, 2.0),
]
NAC_TIP = (-3.14, -0.06)
NAC_WELL_Y = (-2.25, 0.25)
NAC_WELL_TOP_FWD = 0.15     # well roof under the wing box (strut bay)
NAC_WELL_TOP_AFT = 0.57     # roof over the retracted wheel (wing skin cut away above it)
NAC_WELL_STEP_Y = -0.85
NAC_WELL_HALF_X = 0.33

# ---------------------------------------------------------------- tail
STAB_Z = 0.84
STAB_ROOT_X = 0.40
STAB_TIP_X = 3.48
STAB_LE = lambda ax: -7.00 - 0.199 * (ax - 0.98)        # -7.00 at 0.98, -7.45 at 3.24
ELEV_HINGE_Y = -8.11
ELEV_TE = lambda ax: -9.01 if ax < 2.9 else -9.01 + (ax - 2.9) / 0.29 * 0.55
ELEV_X = (0.47, 3.19)
FIN_X = 3.35
FIN_Z = (0.00, 2.64)
RUDDER_HINGE_Y = -8.12
# fin outline: z -> (LE y, rudder TE y)
FIN_TABLE = [(0.00, -7.86, -8.30), (0.05, -7.55, -8.55), (0.15, -7.35, -8.72), (0.35, -7.20, -8.90),
             (0.60, -7.12, -8.98), (1.00, -7.18, -8.99), (1.50, -7.27, -8.97), (2.00, -7.35, -8.95),
             (2.25, -7.40, -8.90), (2.40, -7.44, -8.82), (2.52, -7.52, -8.68), (2.60, -7.64, -8.48),
             (2.64, -7.85, -8.22)]

# ---------------------------------------------------------------- gear (extended pose)
GROUND_Z = 2.64 - 4.98     # fin top - published height
MAIN_WHEEL_R = 0.597       # 47 in tyre
MAIN_WHEEL_W = 0.38
MAIN_PIVOT = (NAC_X, 0.05, -0.15)
MAIN_AXLE = (NAC_X, -0.10, GROUND_Z + MAIN_WHEEL_R)
MAIN_RETRACT_DEG = -88.0   # about +X (Blender); wheel swings aft/up into nacelle
NOSE_WHEEL_R = 0.38
NOSE_WHEEL_W = 0.20
NOSE_PIVOT = (0.0, 3.85, -0.45)
NOSE_AXLE = (0.0, 4.30, GROUND_Z + NOSE_WHEEL_R)
NOSE_RETRACT_DEG = -110.0

# ---------------------------------------------------------------- armament / crew
COCKPIT_EYE = (-0.36, 3.42, 1.10)
TURRET_C = (0.0, 1.82, 1.34)

# ================================================================ v3 rework (2026-10-30, offline worker)
# Feature switches for the generator. New objects are generated by default; nothing the build does not know
# about is wired until B25HBuild reads b25h_v2_contract.json. Prop blur meshes go to a separate FBX so the
# main FBX never shows an unwired opaque disc.
FEATURES = dict(
    torn_breaks=True,        # jagged skin at split planes + spar/stringer stubs + set-back ribs/frames
    copilot_controls=False,  # 2026-11-01 cockpit rebuild: historical H (the user asked for it): no co-pilot controls, the right
                             # seat is the navigator / cannoneer station (earlier the user had asked for a right-hand column)
    propdisc_separate_fbx=True,
)

# split planes that get torn (axis, coordinate, parts on the two sides)
FUS_TORN = {4.55: ('fus_nose', 'fus_cockpit'), 2.62: ('fus_cockpit', 'fus_forward'),
            1.30: ('fus_forward', 'fus_center'), -1.80: ('fus_center', 'fus_rear'), -6.10: ('fus_rear', 'fus_tail')}
WING_TORN = {2.95: ('wing_inner', 'wing_outer'), 6.15: ('wing_outer', 'wing_tip')}
TEAR_AMP_FUS = 0.06       # m, max skin-edge displacement along the axis
TEAR_AMP_WING = 0.08
TEAR_SETBACK = 0.10       # m, frame / rib set back from the tear plane inside each part

# crew of five (Blender coords). eye = head position; seat = cushion centre
CREW = {
    'pilot':    dict(seat=(-0.36, 3.28), eye=(-0.36, 3.42, 1.10), part='fus_cockpit', hatch='hatch_cockpit_top'),
    'navigator': dict(seat=(0.36, 3.28), eye=(0.36, 3.42, 1.08), part='fus_cockpit', hatch='hatch_entry_fwd'),
    'engineer': dict(seat=(0.0, 1.70), eye=(0.0, 1.62, 1.50), part='fus_forward', hatch='hatch_entry_fwd'),
    # 1.8.13 r2 (offline L): radio seat 0.50 m and tail seat 0.10 m forward - the AN/M2 receivers + grips (0.86 m inboard of the L waist
    # socket, 0.52 m forward of the tail trunnion) swing through where they stood
    'radio':    dict(seat=(0.0, -2.25), eye=(0.0, -2.12, 0.78), part='fus_rear', hatch='hatch_entry_rear'),
    'tail':     dict(seat=(0.0, -8.82), eye=(0.0, -8.92, 0.86), part='fus_tail', hatch='hatch_entry_rear'),
}

# escape / entry hatches (fuselage-skin cut-outs; y range, half width)
HATCH_FWD_Y = (1.42, 1.78)
HATCH_FWD_HALF_X = 0.27
HATCH_REAR_Y = (-5.30, -4.70)
HATCH_REAR_HALF_X = 0.25
HATCH_TOP_Y = (3.07, 3.73)       # cockpit roof escape hatch (glazed, in the canopy)
HATCH_TOP_HALF_X = 0.30

# defensive armament
TURRET_RING_Z = 1.18             # top of the turret ring structure (fus_forward)
STOCK_M2_MUZZLE = (0.0, 1.200, 0.046)   # muzzle in the stock 50cal_doorGun_barrel mesh frame (Blender local: x, fwd, up)
TAIL_GUN_PIVOT = (0.0, -9.55, 0.40)   # el trunnion; opening in the tail cap 0.25 m aft

# instrument panel (raked 8 deg back at the top), y of the panel face at z=0.70
PANEL_Y = 4.26
PANEL_RAKE = 8.0
