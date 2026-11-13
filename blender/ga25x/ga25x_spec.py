"""GA-25X design numbers: the B-25H spec (blender/v2/b25h_spec.py) with the GA-25X changes applied IN MEMORY.

The GA-25X is the B-25H airframe redesigned with near-future tech (docs/ga25x_design.md). Same outer lines (fuselage
table, gull wing, twin tail, 20.60 m span), so every B-25H builder is reused by import; only the values below differ.
apply() must run BEFORE b25h_parts / b25h_v3* are (re)loaded, because b25h_parts computes REQUIRED_Y and the turret
hole range from the spec at import time. Nothing here changes b25h_spec.py on disk or the B-25H build.

Blender space as the B-25H: nose +Y, up +Z, right wing +X, metres.
"""
import math

CHANGES = dict(
    # ---- fuselage: longer solid modern nose (76 mm, radar in the skin). Length nose tip -> tail end = 16.13 m.
    NOSE_TIP_Y=6.18,              # B-25H 5.94; + sensor tail cone tip at -9.955 -> 16.13 m overall
    NOSE_TIP_Z=0.02,              # B-25H 0.08: lower, more pointed radome-like nose (cannon on the axis)
    # bomb bay 'slightly expanded': 2.65 -> 2.95 m long, half width 0.60 -> 0.66 m (stays inside the fus_center split)
    BAY_Y=(-1.70, 1.25),
    BAY_HALF_X=0.66,
    # waist windows and tail glazing removed (flat sensor panels / sensor tailcone instead)
    WAIST_L_Y=(-99.0, -98.9),
    WAIST_R_Y=(-99.0, -98.9),
    TAIL_GLASS_Y=-99.0,
    # 6-blade composite props, 3.90 m (B-25H 3.86 m 3-blade)
    PROP_R=3.90 / 2,
)

# slim turboprop nacelles (visual pass 2026-10-31): ~20 % narrower than the B-25H radial nacelle ahead of and over the
# gear well, low smaller firewall ring (the cowl tapers from it into the spinner), aft taper and well heights unchanged so
# the B-25H gear well, retracted wheel (half width incl. fork 0.30, trunnion 0.35) and the wing box stay inside.
NAC_TABLE = [  # y, half width, z bottom, z top, superellipse n
    (1.62, 0.455, -0.530, 0.570, 2.2),
    (1.40, 0.470, -0.580, 0.625, 2.3),
    (1.10, 0.488, -0.645, 0.705, 2.4),
    (0.80, 0.502, -0.715, 0.785, 2.4),
    (0.50, 0.515, -0.760, 0.840, 2.4),
    (0.25, 0.520, -0.770, 0.840, 2.4),
    (0.00, 0.525, -0.770, 0.820, 2.4),
    (-0.40, 0.545, -0.765, 0.790, 2.3),
    (-0.80, 0.570, -0.760, 0.740, 2.3),
    (-1.20, 0.585, -0.750, 0.680, 2.3),
    (-1.60, 0.565, -0.720, 0.610, 2.3),
    (-2.00, 0.505, -0.670, 0.530, 2.2),
    (-2.25, 0.450, -0.620, 0.480, 2.2),
    (-2.50, 0.370, -0.550, 0.420, 2.1),
    (-2.75, 0.270, -0.460, 0.340, 2.0),
    (-2.95, 0.170, -0.360, 0.250, 2.0),
    (-3.08, 0.090, -0.280, 0.180, 2.0),
]

# two crew side by side in the armoured capsule: pilot left, weapons officer ("the cannoneer") right
CREW = {
    # 0.3.0: ejection seats (seat centre moved forward under the eye: backrest at eye height ~0.24 m behind the eye);
    # both crew leave through the jettisoned canopy (hatch_cockpit_top = aft canopy section over both seats)
    # 0.3.1 (stock-seat kitbash): both eyes at 1.050 so the STOCK ejection seat under each crew figure (seat headbox corner
    # 0.30 m above the eye) stays inside the canopy panels (eye 1.10 put it 32 mm through the pilot panel, 1.08: 12 mm; 1.065 left 0.2 mm, 1.055 3 mm: 1.050 = 8 mm clearance to the inner shell).
    'pilot': dict(seat=(-0.36, 3.455), eye=(-0.36, 3.42, 1.050), part='fus_cockpit', hatch='hatch_cockpit_top'),
    'wso':   dict(seat=(0.36, 3.455), eye=(0.36, 3.42, 1.050), part='fus_cockpit', hatch='hatch_cockpit_top'),
}

# 0.3.0: no tail gunner -> no raised glazed tail-gunner fairing ('hump', B-25H rows -7.66 .. -9.72 rise to z 1.365).
# The top line now runs down smoothly from the fin/stabiliser area into the sensor tail cone (same end ring at -9.72,
# so the tail cone and the tail-hook keel are unchanged); the stabiliser root (z 0.84 + half thickness) stays inside.
TAIL_TOP = [(-6.87, 1.000, 0.680), (-7.27, 0.985, 0.700), (-7.66, 0.970, 0.720), (-8.05, 0.950, 0.740),
            (-8.45, 0.925, 0.760), (-8.84, 0.895, 0.780), (-9.23, 0.850, 0.800), (-9.45, 0.810, 0.820),
            (-9.62, 0.765, 0.840), (-9.72, 0.720, 0.850)]   # (y, z top, top-corner radius factor)


def tail_table(fus_table):
    by = {r[0]: r for r in TAIL_TOP}
    out = []
    for row in fus_table:
        y, hw, zb, zt, rf = row
        if y in by:
            zt, rf = by[y][1], by[y][2]
        out.append((y, hw, zb, zt, rf))
    return out

# ---- GA-25X specific placements (Blender coordinates)
CANNON_Z = -0.06                 # 76 mm on the centreline, just below the nose axis
CANNON_BREECH_Y = 3.95           # autoloader + breech behind the radar bulkhead (fus_nose / fus_cockpit)
CHIN_TURRET = (0.0, 5.10, None)  # EO/IR/designator ball under the nose (z = skin bottom - 0.10)
LASER_C = (0.0, 1.82)            # 0.1.0-0.2.0 dorsal laser turret centre (the B-25H top-turret ring); 0.3.0: faired over
# 0.3.0 (user): laser turret moved to the belly just behind the bomb bay (the dorsal one could not engage missiles from
# below). Ventral fairing y -1.84 .. -2.96 (bay doors end at -1.70; fus_center/fus_rear split -1.80).
LASER_BELLY_Y = -2.40
LASER_FAIRING_DEPTH = 0.085      # turret ring plane below the belly skin
LASER_MIN_EL = 10.0              # deg below the horizon (mount frame is inverted): clears both prop discs (7.6 deg) and the
                                 # open main-gear doors; open bomb doors mask the forward-low sector (see check_laser_ga25x)
# 4 pylons per wing (user, 2026-10-31): root (wing_inner, between fuselage and nacelle) + three on wing_outer.
# Spacing from the stock mount widths (half widths: AGR-24 x12 0.415, AGM-48 x3 0.391, AGM-68 0.247, AGR-24 x4 0.195,
# MMR-S3 0.176, PAB-250LR 0.142; measured read-only from the user's export): the mid pylon takes single stores only.
PYLON_X = dict(root=1.55, inner=4.10, mid=4.95, outer=5.80)
HP_BOMBBAY = (0.0, -0.225, -0.18)        # bay centre; paired racks at x = +-0.33
BAY_RACK_X = 0.33
TAILHOOK_PIVOT = (0.0, -7.10, -0.30)     # under the aft fuselage (2.30 m hook reaches the deck at ~64 deg)
SENSOR_PANEL_Y = (-3.95, -2.85)          # old waist-window band: flat sensor panels + flare dispensers
TAILCONE_TIP_Y = -9.955


def apply(S):
    """patch the (already imported) b25h_spec module object."""
    for k, v in CHANGES.items():
        setattr(S, k, v)
    S.NAC_TABLE = NAC_TABLE
    S.CREW = CREW
    S.FUS_TABLE = tail_table(S.FUS_TABLE)
    S.SPLITS = dict(S.SPLITS)
    S.SPLITS['fus_nose'] = (S.NOSE_TIP_Y, S.NOSE_BASE_Y)
    S.FEATURES = dict(S.FEATURES)
    S.FEATURES['copilot_controls'] = True
    S.GA25X = True
    return S
