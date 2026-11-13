"""Hawker Nimrod Mk I: dimensions (metres, Blender frame: x right, y forward, z up; z = 0 thrust line).

Values measured on the War Thunder reference (blender/nimrod/measure_wt.py, numbers only; see docs/nimrod_design.md 1)
and checked against the spec (span ~10.2, length ~8.1, height ~3.0, prop ~3.3 m).
"""
import math

# ---------------------------------------------------------------- fuselage stations: (y, half width, top z, bottom z, side exponent)
FUS = [
    (2.38, 0.300, 0.300, -0.330, 2.2),
    (2.25, 0.335, 0.333, -0.358, 2.3),
    (2.00, 0.385, 0.400, -0.500, 2.5),
    (1.75, 0.420, 0.440, -0.600, 2.7),
    (1.40, 0.450, 0.465, -0.600, 2.9),
    (1.00, 0.452, 0.500, -0.600, 3.0),
    (0.60, 0.452, 0.520, -0.600, 3.0),
    (0.20, 0.452, 0.550, -0.600, 3.0),
    (0.00, 0.452, 0.565, -0.600, 3.0),
    (-0.20, 0.452, 0.580, -0.602, 3.0),
    (-0.40, 0.452, 0.600, -0.604, 3.0),
    (-0.70, 0.445, 0.620, -0.605, 3.0),
    (-1.00, 0.430, 0.705, -0.605, 3.0),
    (-1.30, 0.410, 0.610, -0.603, 2.9),
    (-1.50, 0.398, 0.540, -0.600, 2.9),
    (-1.90, 0.368, 0.470, -0.588, 2.8),
    (-2.30, 0.337, 0.413, -0.568, 2.7),      # 1.4.0: rear fuselage re-measured on the reference (sections at -2.3 .. -4.4)
    (-2.90, 0.290, 0.330, -0.535, 2.6),
    (-3.50, 0.228, 0.256, -0.487, 2.5),
    (-4.10, 0.140, 0.225, -0.425, 2.4),
    (-4.50, 0.035, 0.205, -0.390, 2.2),
]
FUS_123_REAR = [(-2.30, 0.336, 0.418, -0.570, 2.7), (-2.90, 0.272, 0.340, -0.525, 2.6), (-3.50, 0.195, 0.300, -0.445, 2.5),
                (-4.10, 0.105, 0.272, -0.335, 2.4), (-4.50, 0.030, 0.255, -0.255, 2.2)]
ENGINE_AFT_Y = 0.0        # fus_engine: y >= 0 ; root (centre): 0 .. -1.5 ; fus_rear: < -1.5
CENTRE_AFT_Y = -1.5
COCKPIT_Y = (-1.05, -0.40)  # opening
COCKPIT_SILL_Z = 0.50
# 1.8.0 (user: "mesh issues at the cockpit edge": the opening was a rectangle cut across the decking): rounded opening in plan (superellipse:
# blunt front behind the windscreen, U-shaped rear like the reference), the skin of the cockpit rows rebuilt on the exact surface up to the
# hole edge, the leather roll follows the new edge. OPENING_EXP = (front, rear) exponents; FD-32 overrides (more square, under its canopy).
OPENING_ROUND = True
OPENING_EXP = (5.0, 2.4)
OPENING_ZCUT = 0.44            # the cockpit rows' skin is rebuilt from the ring point just below this height upward

# ---------------------------------------------------------------- wings (LE / TE in y, z of the chord line at the LE)
UP_LE, UP_TE = 1.28, -0.20
UP_Z = 0.955
UP_DIHEDRAL = 1.0
UP_TIP_X = 5.13
UP_CENTRE_X = 0.80
UP_CUTOUT_X, UP_CUTOUT_TE = 0.40, 0.18          # trailing-edge cut-out over the cockpit
AIL_X = (1.89, 4.90)
AIL_HINGE_S = 0.70                              # chord fraction of the aileron hinge
LO_LE, LO_TE = 0.40, -1.00
LO_ROOT_X, LO_TIP_X = 0.44, 4.46
LO_Z = -0.545
LO_DIHEDRAL = 2.0
INCIDENCE = 1.5
T_WING = 0.11
STRUT_X = 3.45                                  # interplane N-strut (upper end)
STRUT_X_LO = 3.02                               # 1.4.0: lower end (reference front view: the struts lean in, 3.33 -> 2.97)

# ---------------------------------------------------------------- tail
STAB_LE, STAB_HINGE, STAB_TE, STAB_Z = -3.72, -4.17, -4.84, 0.16     # 1.4.0: STAB_Z 0.205 -> 0.16 (reference: 0.11 .. 0.21)
STAB_Z_123 = 0.205
STAB_TIP_X = 1.575
FIN_LE_ROOT, FIN_HINGE, RUDDER_TE = -3.70, -4.47, -5.30
FIN_ROOT_Z, FIN_TOP_Z, RUDDER_BOTTOM_Z = 0.27, 1.36, -0.41
# 1.4.0 tail planform (user review 2, shot 1/2/15/16): traced on the reference top / side views (numbers only).
# Elevator hinge line moved aft to the reference's -4.38 (was -4.17) with a horn balance (front at -4.17) outboard of x 1.26;
# stabiliser LE straight to x 1.10 then a round tip; elevator TE deepest (-4.905) at x 0.5, rounded into the root and the tip.
ELEV_HINGE = -4.38
ELEV_HORN_X = 1.26
ELEV_ROOT_X = 0.13                   # elevator inner end (clear of the rudder at full deflection, outside the tail cone)
STAB_LE_TABLE = [(0.0, -3.705), (1.10, -3.705), (1.16, -3.72), (1.21, -3.735), (1.26, -3.755), (1.31, -3.785), (1.36, -3.815),
                 (1.41, -3.85), (1.46, -3.90), (1.51, -3.97), (1.545, -4.05), (1.565, -4.12), (1.575, -4.20)]
ELEV_TE_TABLE = [(0.13, -4.60), (0.16, -4.64), (0.21, -4.71), (0.26, -4.785), (0.31, -4.825), (0.36, -4.865), (0.41, -4.89), (0.46, -4.90),
                 (0.51, -4.905), (0.60, -4.89), (0.80, -4.845), (1.00, -4.80), (1.10, -4.77), (1.20, -4.74), (1.30, -4.70), (1.40, -4.625),
                 (1.46, -4.56), (1.51, -4.475), (1.545, -4.38), (1.565, -4.28), (1.575, -4.20)]
# fin: LE from the fuselage spine (-3.62, z 0.25) curving aft to the top (z 1.19); post at the rudder hinge; rudder (hinge -4.47)
# chord aft of the hinge per height, rounded bottom and top; mass-balance horn above the fin top on a short post
FIN_LE_TABLE = [(0.22, -3.60), (0.30, -3.66), (0.40, -3.70), (0.45, -3.72), (0.55, -3.762), (0.65, -3.81), (0.75, -3.87), (0.85, -3.95),
                (0.95, -4.04), (1.05, -4.16), (1.12, -4.27), (1.17, -4.37), (1.19, -4.45)]
FIN_TOP = 1.19
RUDDER_CHORD_TABLE = [(-0.41, 0.06), (-0.383, 0.18), (-0.333, 0.34), (-0.283, 0.47), (-0.233, 0.55), (-0.183, 0.62), (-0.133, 0.66),
                      (-0.083, 0.69), (-0.033, 0.71), (0.017, 0.72), (0.067, 0.73), (0.117, 0.745), (0.30, 0.75), (0.47, 0.75),
                      (0.57, 0.735), (0.667, 0.72), (0.767, 0.69), (0.867, 0.655), (0.967, 0.605), (1.067, 0.53), (1.117, 0.48),
                      (1.167, 0.41), (1.207, 0.32), (1.232, 0.20), (1.245, 0.06)]
RUDDER_TOP = 1.245
TAIL_STRUT_Y = (-3.87, -4.33)        # front / rear tail strut planes (both meet the stabiliser underside at x 0.69)
TAIL_STRUT_X = 0.69
# tail SKID (1.4.0): the real aircraft had a sprung skid, not a wheel. The game's LandingGear contact is unchanged (axle TAIL_AXLE,
# radius TAILWHEEL_R): the skid shoe's bottom sits exactly on the old tyre's bottom, so the ground attitude is the same.
SKID_PIVOT = (0.0, -3.91, -0.46)     # skid arm root (fuselage bottom fitting)
SKID_SHOE_Y = (-4.08, -4.24)         # shoe length along the ground
# visible arrester hook (1.4.0): an A-frame lying under the belly behind the yellow band, hinged at the belly, claw at the rear.
# It is a separate visual mesh (`hook_visual`, child of fus_rear) driven by B25H.Instruments to follow the functional TailHook,
# whose own mesh is hidden. Deployed, its claw ends where the functional hook tip ends (functional: hinge HOOK_PIVOT, 2.37 m, -65 deg).
HOOKV_PIVOT = (0.0, -1.79, -0.60)
HOOKV_STOW = 2.0                     # deg, tip up (lies along the belly)
HOOKV_LEN = 1.718                    # hinge -> claw catch point; with HOOKV_DEPLOY puts the claw on the functional tip (check)
HOOKV_DEPLOY = -58.7                 # deg
HOOKV_HALF_SPAN = 0.27               # hinge lugs at x +-0.27
# spinner (1.4.0, shot 11/12): pointed cone with a ring joint, starter dog at the tip, fills the cowl front ring
SPINNER2_R = 0.285                   # back plate radius (inside the cowl front ring)
SPINNER2_TIP_Y = 2.98
# ring-and-bead sight (1.4.0, shot 8): ring on a post just ahead of the windscreen, bead post forward on the cowl decking
RING_SIGHT_C = (-0.051, 0.118, 0.696); RING_SIGHT_R = 0.050
BEAD_POST = (-0.051, 0.785, 0.685)
# windscreen (1.4.0, shot 8/17): small three-pane screen, top 0.71, top width +-0.15, wrapping to +-0.27 at the decking
WS_Y, WS_TOP_Z, WS_TOP_HW, WS_BOT_HW = -0.345, 0.710, 0.150, 0.265

# ---------------------------------------------------------------- propeller / engine
PROP_Y = 2.47               # blade plane
SPINNER_TIP_Y = 2.88
PROP_R = 1.65
SPINNER_R = 0.275

# ---------------------------------------------------------------- undercarriage (flight attitude = model attitude)
MAIN_AXLE = (0.905, 0.85, -1.650)             # round 9 (user: tips over on landings / spawn): 0.15 m forward = tail-up CoM angle ~16 deg (was 11.9) > brake friction 0.20 (fd32_design 21.4)
WHEEL_R, WHEEL_W = 0.355, 0.13
TAIL_AXLE = (0.0, -4.15, -0.570)
TAILWHEEL_R = 0.11
GROUND_LEVEL_Z = MAIN_AXLE[2] - WHEEL_R          # -2.005 (level attitude)
THREE_POINT_DEG = math.degrees(math.atan2((TAIL_AXLE[2] - TAILWHEEL_R) - GROUND_LEVEL_Z, MAIN_AXLE[1] - TAIL_AXLE[1]))

# ---------------------------------------------------------------- hook, guns, racks
# 1.2.2: hinge INSIDE the rear fuselage at the CG height (was (0, -1.80, -0.615), length 1.60, under the belly). TailHook trails the
# hook along the cable while hooked (ApplyForce swings it toward the force), so the line of pull passes through the hinge: 0.59 m
# below the CG it pitched the aircraft onto its nose in the game test (pitch 7 -> -44). At the CG height the pull has no nose-down
# arm (tools/flightmodel/nimrod_arrest.py). Stowed, the bar lies inside the fuselage; deployed it leaves the belly at y ~ -1.95.
# The hinge is also TailHook's Linecast origin: it must sit inside the fus_rear collider (y < -1.5) so the cast never hits our own hull.
HOOK_PIVOT = (0.0, -1.68, 0.08)    # 0.10 m above the CG (CG z -0.023), 0.18 m behind the root / fus_rear split
HOOK_LEN = 2.37             # reaches 6 cm below the level wheel-contact plane at -65 deg
HOOK_STOW_UP = 2.0          # deg: stowed tip up (inside the fuselage, 6 cm under the fin root); 1.2.1: 3.5 under the belly
HOOK_PIVOT_121 = (0.0, -1.80, -0.615); HOOK_LEN_121 = 1.60; HOOK_STOW_UP_121 = 3.5      # the game-tested 1.2.1 hook (kept for the arrest model's comparison)
HOOK_DEPLOY = -65.0         # deg: deployed. 1.2.1: -24 left the tip 0.7 m above the wires in a level touchdown (game test); -65 puts it
                            # 6 cm below the wheel-contact plane at 0 deg pitch (TailHook lifts it on contact with the deck)
GUN_X, GUN_Z = 0.165, 0.455
GUN_BREECH_Y, GUN_BODY_Y, GUN_TROUGH_END_Y = -0.40, 0.72, 1.58
MUZZLE_Y = PROP_Y + 0.19    # bullet origins ahead of the disc (synchroniser)
RACK_X, RACK_Y = 1.75, -0.28

# ---------------------------------------------------------------- cockpit
EYE = (0.0, -0.92, 0.745)
PANEL_Y = -0.355             # lower panel face (cockpit v2; layout in nimrod_ck_layout.py)
FLOOR_Z = -0.52

# 1.2.3 CG (contract cg_blender): kept by build_nimrod.py so the 2026-11-02 visual rebuild leaves every contract number unchanged
CG_123 = (0.0, 0.3222, -0.023)

# ---------------------------------------------------------------- masses (kg) for the CG check (Unity builder holds the same table)
MASSES = {'NIMROD1': 300, 'fus_engine': 850, 'prop': 50, 'fus_rear': 50, 'wing_upper_C': 30, 'wing_upper_L': 60, 'wing_upper_R': 60,
          'aileron_L': 5, 'aileron_R': 5, 'wing_lower_L': 55, 'wing_lower_R': 55, 'stab_L': 12, 'stab_R': 12, 'elevator_L': 5,
          'elevator_R': 5, 'fin': 8, 'rudder': 5}
