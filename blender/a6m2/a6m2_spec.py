"""Mitsubishi A6M2 Zero Model 21: reviewed dimensions (round 1, 2026-11-18). NUMBERS ONLY.

Frame (Blender): x right, y forward, z up, metres; z 0 = thrust line (prop axis); y 0 = the War Thunder model origin.
Every table below is in "ours, pre-scale" = War Thunder reference numbers after the axis swap only (WT x fwd / y left / z up ->
ours x = -y_wt, y = x_wt, z = z_wt), measured read-only and hand-reviewed (rounded to 5 mm where the source was noisy):
  nuclearoption-ref/study/a6m2/airframe_fm_work/measure.json, surfaces.json   (design study, docs/a6m2_design.md 1)
  nuclearoption-ref/study/a6m2/r1/sections.json, section_fit.json, parts.json (round 1 measurements, scripts next to them)
Nothing here is a vertex, UV or texture of the reference; nothing under refs/ is opened at build time (stub: no 'refs' path in this file
that the builder reads; tools/stub_tests_a6m2_r1.py asserts it).

pre(p)        ours pre-scale -> built model: uniform x K (9.009 -> 9.06 m), then the 0.127 m spanwise plug per wing at |x| = 2.95 (design 0.1.1).
wt_to_ours(p) WT frame (x fwd, y left, z up) -> built model (the one conversion point of design 0.1 / C3).
span_pre(x)   built |x| -> pre-scale |x| (inverse of the plug: the plug repeats the section at 2.95 / K).
"""
import math

K = 9.06 / 9.009                    # uniform scale (length 9.009 -> 9.06 m)
PLUG_X = 2.95                       # built |x| where the plug starts (outboard of gun 1.92, rack 2.37, gear 1.73, break 2.70)
PLUG = 0.127                        # m per wing: span 11.68 x K + 2 x 0.127 = 12.00
DIHEDRAL_DEG = 5.6
TAN_DIH = math.tan(math.radians(DIHEDRAL_DEG))


def plug_x(xs):
    """x after the uniform scale -> x with the plug (sign kept)."""
    a = abs(xs)
    if a <= PLUG_X:
        return xs
    return math.copysign(a + PLUG, xs)


def plug_z(xs):
    """z offset the plug adds outboard of PLUG_X (the plug carries the dihedral)."""
    a = abs(xs)
    return min(max(a - PLUG_X, 0.0), PLUG) * TAN_DIH if a > PLUG_X else 0.0


def pre(p, plug=True):
    """ours pre-scale point -> built point."""
    x, y, z = p[0] * K, p[1] * K, p[2] * K
    if plug:
        z += plug_z(x)
        x = plug_x(x)
    return (x, y, z)


def wt_to_ours(p_wt, plug=True):
    """War Thunder reference frame (x fwd, y left, z up) -> built model (x right, y fwd, z up)."""
    return pre((-p_wt[1], p_wt[0], p_wt[2]), plug)


def span_pre(xb):
    """built |x| -> pre-scale |x| (the plug repeats the section at PLUG_X / K)."""
    a = abs(xb)
    if a <= PLUG_X:
        return a / K
    if a <= PLUG_X + PLUG:
        return PLUG_X / K
    return (a - PLUG) / K


def span_built(xp):
    """pre-scale |x| -> built |x| (outboard points get the plug)."""
    return abs(plug_x(xp * K))


def lin(tab, x, col=1):
    """piecewise-linear lookup in a table sorted by column 0 (either direction), clamped."""
    t = sorted(tab, key=lambda r: r[0])
    if x <= t[0][0]:
        return t[0][col]
    if x >= t[-1][0]:
        return t[-1][col]
    for a, b in zip(t, t[1:]):
        if a[0] <= x <= b[0]:
            f = (x - a[0]) / (b[0] - a[0]) if b[0] != a[0] else 0.0
            return a[col] + (b[col] - a[col]) * f
    return t[-1][col]


# =============================================================================== targets (design 1, spec numbers)
LENGTH = 9.06                       # spinner tip 2.381 .. rudder / tail-cone tip -6.628 (pre)
SPAN = 12.00
WING_AREA = 22.49                   # design 0.1.1 (plug) ; spec 22.44
NOSE_TIP_Y, TAIL_TIP_Y = 2.381, -6.628

# =============================================================================== fuselage body (closed loft; canopy, cowl lip, fin are separate)
# (y, zt, zb, hw, zw, nt, nb): top / bottom z at the centreline, max half-width hw at height zw, superellipse exponents of the upper and
# lower halves (|x/hw|^n + |dz/dz_half|^n = 1). Measured clean outside the wing / canopy / fin (r1/section_fit.json rms 4-27 mm);
# inside the wing chord (y 0.65 .. -1.85) zb is the hidden body floor INSIDE the wing centre section (-0.45; the belly is the wing's lower
# skin, -0.60 measured); under the canopy (y 0.30 .. -1.98) zt is the hidden deck under the glazing (the cockpit opening is cut from it).
# Fin region (y < -4.35): body without the fin and the stabiliser (measured below z 0.4 / x < 0.3 only). Tail tip = knife fairing to -6.63.
BODY = [
    (1.940, 0.500, -0.535, 0.500, -0.005, 2.1, 1.9),     # cowl lip (outer); r1 review: the reference cowl is near-cylindrical to the lip (top view)
    (1.900, 0.545, -0.600, 0.545, 0.000, 2.1, 1.8),
    (1.800, 0.572, -0.645, 0.572, 0.000, 2.05, 1.75),
    (1.650, 0.582, -0.663, 0.582, 0.000, 2.0, 1.7),
    (1.400, 0.588, -0.677, 0.583, -0.005, 2.0, 1.7),
    (1.210, 0.592, -0.665, 0.582, 0.000, 2.0, 1.7),      # cowl end / cowl-flap hinge 1.206
    (1.028, 0.598, -0.700, 0.548, 0.005, 2.0, 1.6),      # cowl-flap trailing edge (flaps step in to the fuselage)
    (0.900, 0.608, -0.700, 0.566, 0.005, 1.95, 1.6),     # chin (oil cooler) is its own fairing
    (0.650, 0.639, -0.620, 0.565, 0.015, 1.95, 1.7),
    (0.400, 0.672, -0.450, 0.547, 0.000, 2.0, 2.2),      # inside the wing from here
    (0.150, 0.690, -0.450, 0.532, -0.040, 2.0, 2.4),
    (-0.100, 0.690, -0.450, 0.514, -0.050, 2.0, 2.5),
    (-0.350, 0.680, -0.450, 0.505, -0.050, 2.0, 2.5),
    (-0.600, 0.670, -0.450, 0.498, -0.050, 2.0, 2.5),
    (-0.850, 0.665, -0.450, 0.491, -0.050, 2.0, 2.5),
    (-1.100, 0.660, -0.450, 0.485, -0.040, 2.0, 2.5),
    (-1.350, 0.650, -0.460, 0.481, -0.020, 2.0, 2.5),
    (-1.600, 0.642, -0.480, 0.477, 0.000, 2.0, 2.4),
    (-1.850, 0.640, -0.505, 0.472, 0.000, 2.0, 2.3),
    (-2.100, 0.668, -0.545, 0.464, 0.001, 2.0, 2.3),     # turtle deck behind the rear glazing (top incl. the glazing fairing)
    (-2.350, 0.616, -0.529, 0.453, 0.014, 2.0, 2.4),
    (-2.600, 0.604, -0.512, 0.442, 0.017, 1.95, 2.4),
    (-2.850, 0.591, -0.495, 0.427, 0.020, 1.95, 2.35),
    (-3.100, 0.578, -0.477, 0.411, 0.024, 1.95, 2.3),
    (-3.350, 0.565, -0.458, 0.394, 0.002, 1.95, 2.2),
    (-3.600, 0.547, -0.437, 0.376, 0.005, 1.95, 2.2),
    (-3.850, 0.525, -0.415, 0.357, 0.008, 1.95, 2.1),
    (-4.100, 0.503, -0.393, 0.339, 0.011, 1.95, 2.1),
    (-4.350, 0.472, -0.365, 0.309, 0.020, 1.9, 2.0),
    (-4.600, 0.440, -0.335, 0.279, 0.030, 1.9, 2.0),     # r1 overlay: the belly line stays; the hook lies in a narrow slot (HOOK_SLOT)
    (-4.850, 0.412, -0.300, 0.250, 0.040, 1.9, 2.0),
    (-5.100, 0.385, -0.265, 0.223, 0.050, 1.85, 2.0),
    (-5.350, 0.362, -0.226, 0.185, 0.060, 1.85, 2.0),
    (-5.600, 0.345, -0.200, 0.147, 0.070, 1.8, 2.0),     # tail-wheel housing (station table -0.206)
    (-5.750, 0.340, -0.200, 0.128, 0.075, 1.8, 2.0),
    (-5.850, 0.337, -0.170, 0.112, 0.080, 1.8, 2.0),     # r1 overlay: the tail cone's underside rises later
    (-6.100, 0.330, -0.120, 0.080, 0.080, 1.8, 2.0),
    (-6.350, 0.300, -0.090, 0.047, 0.060, 1.8, 2.0),
    (-6.450, 0.200, -0.070, 0.035, 0.050, 1.8, 2.0),
    (-6.550, 0.090, -0.050, 0.022, 0.020, 1.8, 2.0),
    (-6.628, 0.010, -0.025, 0.006, -0.008, 1.8, 2.0),    # tail-light tip (closed)
]
# part splits along y (design 7.1): fus_engine y >= ENGINE_AFT_Y; root to REAR_FWD_Y; fus_rear to TAIL_FWD_Y; fus_tail aft
ENGINE_AFT_Y = 0.950
REAR_FWD_Y = -2.700                 # the real A6M bolted ring joint aft of the cockpit (WT damage split)
TAIL_FWD_Y = -4.120

# cowl lip / engine front (design 1: lip ring r 0.52 at y 1.87-1.94; opening shows the Sakae front row)
COWL_LIP_Y = 1.940                  # forward face of the lip
COWL_LIP_IN_R = 0.375               # opening radius (inner lip)
COWL_LIP_IN_Y = 1.885               # inner lip line (the lip rolls in over 55 mm)
ENGINE_FACE_Y = 1.560               # front of the cylinder row (seen through the opening)
NOSECASE_R, NOSECASE_Y0 = 0.205, 1.560   # reduction-gear housing in front of the cylinders, up to the spinner back
# gun troughs on the cowl top (design 1 / 2.3): x +-0.206, floor z 0.50, from the muzzle 0.911 to the lip
TROUGH_X, TROUGH_HALF_W, TROUGH_FLOOR_Z = 0.206, 0.034, 0.500
TROUGH_Y = (0.911, 1.940)
# cowl flaps: 8 (4 a side, sides only, ~36 deg below to 46 deg above horizontal), hinge 1.206, TE 1.028, static closed
COWL_FLAP_Y = (1.206, 1.028)
COWL_FLAP_ANG = [(-40.0, -22.96), (-21.76, -4.72), (-3.52, 13.52), (14.72, 31.76), (32.96, 50.0)]   # r1b: 5 even flaps a side, -40..50 deg with 1.2 deg gaps (r1: 4 uneven bands with 2 deg gaps)
# oil cooler chin fairing under the cowl (design 1: to z -0.77 at y ~1.1; intake at (0, 0.873, -0.59) is the aft end)
CHIN = [(1.70, 0.000, -0.630, 0.07), (1.50, 0.000, -0.665, 0.10), (1.25, 0.000, -0.690, 0.115), (1.05, 0.000, -0.705, 0.115),
        (0.85, 0.000, -0.700, 0.105), (0.65, 0.000, -0.680, 0.09), (0.45, 0.000, -0.640, 0.07)]   # r1 overlay: 30 mm shallower   # r1 review: narrower, longer (bottom view)   # (y, x, z_bottom, half width)
EXHAUSTS = [(-0.290, 1.062, -0.590), (0.290, 1.062, -0.590)]            # outlets (design 1)

# =============================================================================== canopy (design 1, 8; glass panels in measure.json)
# base half-width xs on the body surface, apex z (canopy topline), frames; the glazing loft rises from the body surface at xs.
CANOPY_Y = (0.300, -1.985)          # windscreen base front .. rear glazing end
WINDSCREEN_Y = (0.300, -0.250)      # fixed windscreen (front flat + two quarter panels)
HOOD_Y = (-0.264, -1.006)           # sliding hood (0.74 m)
REAR_GLAZ_Y = (-1.006, -1.985)
CANOPY = [   # (y, base half-width xs, apex z, section exponent)
    (0.300, 0.150, 0.672, 2.2), (0.250, 0.205, 0.718, 2.2), (0.175, 0.240, 0.767, 2.3), (0.100, 0.262, 0.816, 2.3),
    (0.025, 0.280, 0.865, 2.4), (-0.050, 0.292, 0.914, 2.4), (-0.125, 0.302, 0.963, 2.5), (-0.200, 0.310, 1.001, 2.6),
    (-0.250, 0.314, 1.016, 2.6), (-0.350, 0.318, 1.024, 2.7), (-0.500, 0.319, 1.031, 2.7), (-0.650, 0.319, 1.034, 2.7),
    (-0.800, 0.318, 1.020, 2.7), (-0.950, 0.316, 0.996, 2.7), (-1.100, 0.306, 0.964, 2.6), (-1.250, 0.304, 0.936, 2.6),
    (-1.400, 0.303, 0.907, 2.6), (-1.550, 0.300, 0.859, 2.5), (-1.700, 0.297, 0.823, 2.5), (-1.850, 0.290, 0.775, 2.4),
    (-1.985, 0.270, 0.705, 2.3)]
CANOPY_EXP_SCALE = 0.68              # r1 review: the reference glazing has strong tumblehome (side panels 0.32 -> 0.20 m half-width)
CANOPY_FRAMES_Y = [0.280, -0.010, -0.250, -0.264, -0.620, -1.006, -1.020, -1.370, -1.750, -1.985]   # frame bars (design 1)
HOOD_SPINE = True                   # centre spine bar on the hood
FRAME_W, FRAME_H = 0.026, 0.006     # frame bar width / height off the glass (r4c: flat narrow strips, coordinator review; r4 0.022 / 0.012)
FRAME_IN = 0.008                     # r4c: inside depth below the glass (green 'interior' face toward the pilot)
CANOPY_SLIDE = 0.50                 # m aft by Canopy.openAmount (design C10; plugin, round 4)
EYE = (0.000, -1.025, 0.790)        # r8: WT headPos y / z, ON THE CENTRELINE (user review 1: WT's +32 mm put pilot, sight and stick off centre)

# =============================================================================== wing (design 1; measure.json wing_port, numbers only)
# (|x| pre, LE y, TE y, chord-line z at LE, at TE, t/c). Centreline values extrapolated along the straight LE (3.97 deg) / TE (-10.1 deg).
WING = [
    (0.000, 0.794, -1.836, -0.466, -0.535, 0.155),
    (0.550, 0.756, -1.738, -0.415, -0.485, 0.160),
    (0.900, 0.732, -1.676, -0.376, -0.445, 0.163),
    (1.150, 0.716, -1.628, -0.351, -0.419, 0.164),
    (1.400, 0.700, -1.584, -0.325, -0.393, 0.164),
    (1.650, 0.680, -1.540, -0.298, -0.367, 0.164),
    (1.900, 0.664, -1.496, -0.273, -0.341, 0.163),
    (2.150, 0.648, -1.452, -0.249, -0.315, 0.163),
    (2.400, 0.628, -1.408, -0.224, -0.287, 0.163),
    (2.650, 0.612, -1.364, -0.200, -0.259, 0.159),
    (2.900, 0.596, -1.320, -0.174, -0.230, 0.154),
    (3.150, 0.576, -1.272, -0.147, -0.202, 0.149),
    (3.400, 0.560, -1.228, -0.121, -0.175, 0.143),
    (3.650, 0.544, -1.184, -0.095, -0.148, 0.137),
    (3.900, 0.528, -1.140, -0.069, -0.121, 0.131),
    (4.150, 0.512, -1.096, -0.043, -0.094, 0.123),
    (4.400, 0.492, -1.052, -0.017, -0.066, 0.116),
    (4.650, 0.476, -1.004, 0.009, -0.038, 0.108),
    (4.900, 0.452, -0.952, 0.035, -0.017, 0.100),
    (5.150, 0.404, -0.888, 0.061, 0.010, 0.093),
    (5.400, 0.324, -0.800, 0.085, 0.045, 0.090),
    (5.650, 0.172, -0.648, 0.106, 0.093, 0.090),
    (5.760, 0.040, -0.500, 0.112, 0.105, 0.090),
    (5.840, -0.240, -0.260, 0.118, 0.118, 0.090),      # tip point (rounded tip from ~5.15)
]
WING_TMAX_S = 0.29                  # max thickness at 29 % chord everywhere (design 1)
WING_CAMBER = 0.020                 # NACA 23xx-like: 2 % camber (our section, design 7.2)
# part breaks (pre |x|; built = span_built): wing_C (on the root) < 0.55, wing_inner < 2.70, wing_mid < 4.71 (+plug), wing_tip < 5.195, wing_fold
WING_BREAKS = [0.950, 2.700, 4.710, 5.195]   # r8e: the root / wing_inner break moved 0.550 -> 0.950, outboard of the root fairing (one root mesh)
FOLD_X = 5.195                      # folding tip hinge (seam modelled, no fold)
# flap (split, lower surface) and aileron (plain): pre |x| span and chord (surfaces.json)
FLAP_X = (0.700, 2.205)              # r8b: inboard end at the fillet foot (0.651 cut into the fillet when deployed)
FLAP_CHORD = [(0.651, 0.495), (1.0, 0.478), (1.4, 0.462), (1.8, 0.44), (2.205, 0.423)]
FLAP_POSES = dict(combat=12.0, takeoff=19.8, landing=60.0)
AIL_X = (2.205, 5.180)          # r8c (game r8b: the aileron tip stayed flat past the fold line): ends 15 mm inboard of the fold hinge FOLD_X 5.195, as the real A6M2 (r8b: 5.367)
AIL_CHORD = [(2.205, 0.418), (2.8, 0.451), (3.3, 0.385), (3.8, 0.363), (4.3, 0.341), (4.8, 0.314), (5.2, 0.269), (5.367, 0.242)]
WING_INCIDENCE_AERO = 1.5           # deg (AeroPart lift normals, design 1); 1.0 on wing_tip / wing_fold

# wing-root fillet (y, foot half-width on the wing top, top z on the body side): Zero's large root fairing, measured from the fan samples
FILLET = [(0.600, 0.600, -0.240), (0.400, 0.640, -0.250), (0.150, 0.650, -0.240), (-0.350, 0.650, -0.200),
          (-0.850, 0.640, -0.190), (-1.350, 0.650, -0.200), (-1.600, 0.680, -0.230), (-1.800, 0.700, -0.260), (-1.950, 0.640, -0.300),
          (-2.100, 0.560, -0.350), (-2.250, 0.470, -0.400)]   # r1 review: the root fairing runs past the TE to y -2.25 (top overlay); r8e: starts at y 0.60 behind the LE and grows over 0.30 m (unioned: no tongue over the LE)

# =============================================================================== tail (design 1; stab_port, fin_profile, surfaces.json)
STAB_Z = 0.175
STAB = [   # (|x| pre, LE y, TE y, half thickness at the root..tip)
    (0.000, -4.150, -5.670, 0.060), (0.300, -4.210, -5.660, 0.058), (0.400, -4.248, -5.644, 0.056), (0.800, -4.376, -5.592, 0.052),
    (1.200, -4.508, -5.540, 0.047), (1.600, -4.640, -5.488, 0.041), (2.000, -4.768, -5.424, 0.036), (2.100, -4.828, -5.388, 0.030),
    (2.200, -4.904, -5.328, 0.022), (2.260, -4.990, -5.250, 0.015), (2.300, -5.120, -5.140, 0.006)]
ELEV_HINGE_Y = -5.230
ELEV_X = (0.340, 2.260)
FIN = [    # (z, LE y, TE y incl. rudder, half thickness) ; rudder hinge y -5.650 (horn balance above z 1.55)
    (0.300, -4.400, -6.360, 0.060), (0.450, -4.520, -6.345, 0.055), (0.600, -4.606, -6.300, 0.049), (0.800, -4.761, -6.220, 0.045),
    (1.000, -4.920, -6.165, 0.040), (1.200, -5.076, -6.115, 0.035), (1.400, -5.231, -6.053, 0.030), (1.500, -5.316, -5.997, 0.023),
    (1.600, -5.442, -5.897, 0.017), (1.650, -5.540, -5.810, 0.011), (1.679, -5.680, -5.700, 0.004)]
DORSAL = [(-4.150, 0.505), (-4.400, 0.520), (-4.520, 0.560)]   # r1 review: lower and shorter (side overlay)     # (y, z) dorsal fin fillet line from the turtle deck to the fin LE
RUDDER_HINGE_Y = -5.650
RUDDER_Z = (0.337, 1.679)
RUDDER_HORN_Z = 1.550               # horn balance: rudder leading edge steps forward to y -5.505 above this

# =============================================================================== landing gear (anim/poses.json, design 1)
MAIN_PIVOT = (1.728, 0.428, -0.303)           # right side (+x); left mirrored
MAIN_WHEEL_DOWN = (1.725, 0.608, -1.614)
MAIN_WHEEL_UP = (0.412, 0.381, -0.430)
MAIN_RETRACT_DEG = 85.0
WHEEL_D, WHEEL_W = 0.634, 0.196
INNER_DOOR_HINGE_X = 0.090                    # well door hinged near the centreline (opens 85 deg when the gear is down)
INNER_DOOR_OPEN = 85.0
SPLIT_BOW = 0.045                             # r6: the door's free edge bows 45 mm outboard at the well centre (reference outline, front-3/4 / bottom views)
DOOR_DOME = 0.026                             # r6: pressed curvature of the inner door (r1b 0.014)
INNER_DOOR_W = 0.230                          # r1 overlay: the reference door is ~0.23 m wide (gear_l3 down: z -0.819..-0.587); the leg cover takes the rest
WELL_R = 0.345                                # round well under the centre section (wheel 0.317 + clearance)
TAIL_PIVOT = (0.000, -5.675, -0.183)
TAIL_WHEEL_DOWN = (0.000, -6.096, -0.354)
TAIL_WHEEL_D, TAIL_WHEEL_W = 0.157, 0.062
TAIL_SEMI_RETRACT_DEG = 38.5                  # visual only (round 1: not driven; the LandingGear stays down)
THREE_POINT_DEG = 12.6

# =============================================================================== hook (design 6)
HOOK_PIVOT = (0.000, -4.536, -0.260)
HOOK_LEN = 0.902
HOOK_STOW_DEG = 1.0                           # stowed: lies aft along the belly recess (TailHook stowedAngle)
HOOK_DOWN_DEG = 40.0                          # deployed 40 deg below the stowed line (TailHook deployedAngle = stow - 40)
HOOK_RECESS_Y = (-4.50, -5.50)
HOOK_SLOT = (-4.480, -5.560, 0.060, -0.120)   # belly slot the stowed hook lies in: y from / to, half-width, roof z (r1 overlay: belly line kept)

# =============================================================================== prop (design 1, 5.3; r1/parts.json)
PROP_PLANE_Y = 2.000                          # blade pitch axis plane (disc y 1.86-2.03)
PROP_TIP_R = 1.497                            # pre-scale (built 1.506; game bladeLength 1.45 + hub)
SPINNER = [(1.860, 0.249), (1.950, 0.249), (2.050, 0.241), (2.120, 0.222), (2.200, 0.196), (2.280, 0.155), (2.340, 0.104),
           (2.370, 0.062), (2.381, 0.000)]    # (y, r)
BLADE = [  # (r, chord, t/c, blade angle deg)
    # r1b (coordinator review of the r1 closeups): narrower blade, max chord 0.215 at r 0.50 (~1/3 R), round shank at the root,
    # elliptic rounded tip from r 1.38 to the tip radius (unchanged 1.497), twist 62 -> 19 deg (was 60 -> 21: visible now the chord is narrower)
    (0.200, 0.085, 0.60, 62.0), (0.280, 0.125, 0.36, 57.0), (0.380, 0.180, 0.21, 50.0), (0.500, 0.215, 0.14, 43.0),
    (0.650, 0.212, 0.11, 37.0), (0.850, 0.200, 0.09, 31.0), (1.050, 0.185, 0.08, 27.0), (1.250, 0.165, 0.07, 23.5),
    (1.380, 0.145, 0.065, 21.5), (1.420, 0.136, 0.063, 21.0), (1.450, 0.119, 0.062, 20.5), (1.470, 0.098, 0.061, 20.0),
    (1.485, 0.071, 0.060, 19.5), (1.494, 0.040, 0.060, 19.2), (1.497, 0.016, 0.060, 19.0)]

# =============================================================================== guns, racks, details (design 2.3)
TYPE97_MUZZLE = (0.206, 0.911, 0.543)          # visible muzzle / flash in the trough (right; left mirrored)
TYPE97_BULLET_Y = 2.220                        # synchroniser: bullet origins 0.19 m ahead of the blade plane
TYPE97_RECEIVER = ((0.238, 0.55, 0.51), (0.911, 0.584))  # |x| max, y range start, z ...
TYPE99_MUZZLE = (1.916, 0.657, -0.272)         # flush with the LE at the gun (right; left mirrored)
TYPE99_BARREL_PROUD = 0.180                    # barrel stub proud of the LE (real Model 21 photos)
TYPE99_BULLET_Y = 0.770
TYPE99_BODY = (1.795, -0.005, -0.290)
RACK = (2.358, -0.125, -0.375)                 # 60 kg rack top on the wing skin (right; tilted 6.5 deg to hang plumb)
RACK_TILT_DEG = 6.5
RACK_HANG = (2.370, -0.126, -0.491)
SPECIAL_HANG = (0.000, -0.432, -0.821)         # centre (Special) rack hang point (round 3)
# round 2 / 3 stores (our own models; nominal published dimensions, not the WT meshes). Profiles: (distance from the nose, radius), m.
NO6_PROFILE = [(0.000, 0.000), (0.020, 0.040), (0.060, 0.068), (0.120, 0.088), (0.200, 0.098), (0.260, 0.100), (0.700, 0.100),
               (0.800, 0.090), (0.920, 0.068), (1.000, 0.058), (1.045, 0.000)]      # Type 97 No.6 60 kg: 1.05 m, 0.20 m dia
NO6_FINS = (0.800, 1.045, 0.130)               # fin y from / to (from the nose), fin tip radius; box-tail ring at the tip
NO6_MASS = 60.0
TOKKO_PROFILE = [(0.000, 0.000), (0.030, 0.060), (0.090, 0.100), (0.180, 0.130), (0.300, 0.146), (0.400, 0.150), (1.150, 0.150),
                 (1.330, 0.132), (1.520, 0.100), (1.680, 0.082), (1.750, 0.000)]    # 250 kg charge (Type 99 No.25-like): 1.75 m, 0.30 m dia
TOKKO_FINS = (1.330, 1.750, 0.205)
TOKKO_MASS = 250.0
NO6_RACK_LEN, CENTRE_RACK_LEN = 0.70, 0.90
PITOT = (-4.740, (0.851, 1.169), 0.018)        # left wing: x, tube y range, z
MAST_BASE = (0.000, -1.850, 0.800)                    # r1 review: raked forward (side overlay)
MAST_TOP = (0.000, -1.700, 1.573)
WIRE_FIN = (0.000, -5.472, 1.600)
NAV_LIGHTS = dict(L=(-5.80, 0.0, 0.118), R=(5.80, 0.0, 0.118))   # tip lenses (period lamp glass, no light source)

# =============================================================================== mass / CoM (design 5.3; fm/masses.py)
MASSES = {   # AeroPart masses (kg)
    'A6M2': 240, 'fus_engine': 895, 'prop': 145, 'fus_rear': 45, 'fus_tail': 42,     # r1b (in-game spawn 1,985 kg vs 2,350): + pilot 80 (root), oil + accessories 150 (engine), tail wheel 8; main gear 40 + 40 on wing_inner below. r1: 160 / 745 / 145 / 45 / 34
        # r1: design 220/640/140/70/40 moved forward: by the Unity check rule (parts at collider-bounds centres, fuel in its tank part) the design masses gave 34-35 % MAC
    'wing_inner_L': 165, 'wing_inner_R': 165, 'wing_mid_L': 60, 'wing_mid_R': 60, 'wing_tip_L': 14, 'wing_tip_R': 14,
    'wing_fold_L': 10, 'wing_fold_R': 10, 'aileron_L': 12, 'aileron_R': 12, 'flap_L': 8, 'flap_R': 8,
    'stab_L': 12, 'stab_R': 12, 'elevator_L': 5, 'elevator_R': 5, 'fin': 12, 'rudder': 8}
MAC = 2.016                          # built (2.005 x K)
MAC_LE_Y = 0.627                     # pre-scale (built x K)
COM_MAC_BAND = (0.27, 0.30)
