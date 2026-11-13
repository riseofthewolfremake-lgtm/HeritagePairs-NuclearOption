"""FD-32 Nimrod: dimensions that differ from the Hawker Nimrod Mk I (docs/fd32_design.md 5). Everything else is nimrod_spec.

apply() patches the imported nimrod_spec module IN MEMORY (the GA-25X precedent: reuse the parent's modules, never edit them).
Frame as nimrod_spec: Blender x right, y forward, z up, metres; z = 0 thrust line.
"""
import nimrod_spec as S

# ---------------------------------------------------------------- propeller: 4-blade composite, 3.0 m (all stores launch outside the disc)
PROP_R = 1.50
BLADES = 4
# ---------------------------------------------------------------- rudder: chord aft of the hinge x 1.15 (larger rudder, Nimrod II style)
RUDDER_SCALE = 1.15
# ---------------------------------------------------------------- lower-wing flaperons (upper wing keeps the Mk I aileron span 1.89-4.90)
FLAP_LO_X = (1.00, 3.90)
# ---------------------------------------------------------------- pylons (x, Blender y of the hardpoint, pylon depth below the lower surface)
PYLONS = {'inner': 1.80, 'outer': 2.55}
PYLON_Y = -0.28
PYLON_DEPTH = 0.12
PYLON_CHORD = 0.62
# ---------------------------------------------------------------- sensor ball in the old radiator bay (stowed / deployed centre)
BALL_Y = 0.46
BALL_R = 0.165
BALL_Z_STOWED = -0.425            # round 11 (user: the stowed ball clipped the belly): fully inside the bay well, bottom 1 cm above the skin (-0.600); was -0.53
BAY_DEPTH = 0.42                 # well liner from the skin up to its cap (cap z -0.18; the fal ball's top flange reaches -0.218 stowed)
BAY_CUT_R = 0.202                # round 11: the belly skin (and its inner skin) is cut open inside this radius (the liner sits at BAY_R)
SENSOR_ARM = 3.0                 # m: the Unity ball arm pivot ahead of the ball (travel 0.375 m -> 7.2 deg, drift 23 mm < bay clearance 40 mm)
BALL_Z_DEPLOYED = -0.80
BAY_R = 0.205
# ---------------------------------------------------------------- canopy: windscreen + sliding hood (Sea Gladiator style)
WS_BASE_Y, WS_TOP_Y, WS_TOP_Z = -0.30, -0.44, 0.955
HOOD_Y = (-0.46, -1.88)          # round 3: canopy front arch / rear end on the turtle deck (after the stretch)
HOOD_TOP_Z = 1.10                # round 3: clears the stock seat's head box (top 1.014) by ~8 cm
HOOD_SILL_Z = 0.515
HOOD_HW = 0.345                  # half width at the sill
SLIDE_PIVOT_DROP = 10.0          # (studied, not used: an arc slide 10 m below drives the hood sills into the headrest fairing)
SLIDE_DEG = 3.0
HOOD_OPEN_DEG = 30.0             # the canopy opens on the ground by tilting up about its rear end (stock Canopy hinge)
# 1.8.3 canopy redesign (blender/fd32/fd32_canopy183.py; user: "right now it looks so stupid"): raked wrap windscreen from the decking at
# y -0.26 to a slim arch at -0.66, bubble hood to -1.615 (top 1.066) faired into a raised spine; the values above stay for the 1.8.2 canopy
# (fd32_canopy183.ENABLED False). These are the ones the contract / checks read.
CANOPY_183 = True
CG_182 = (0.0, 0.3024, 0.0735)    # 1.8.2 contract cg_blender (rounded 0.1 mm): build_fd32 keeps the CG within 5 mm of it
if CANOPY_183:
    WS_BASE_Y = -0.22
    HOOD_Y = (-0.72, -1.615)
    HOOD_TOP_Z = 1.066
    HOOD_SILL_Z = 0.55
# ---------------------------------------------------------------- 12.7 mm guns in the Mk I troughs
GUN_R, JACKET_R = 0.0115, 0.021
# ---------------------------------------------------------------- masses (kg, Unity builder holds the same table): empty ~1,500; battery
# packs + motor + turbogenerator in fus_engine put the CG at the Mk I's (y ~0.30, 0.4 m behind the main axles)
MASSES = {'FD32': 255, 'fus_engine': 805, 'prop': 45, 'fus_rear': 55, 'wing_upper_C': 32, 'wing_upper_L': 62, 'wing_upper_R': 62,
          'aileron_L': 5, 'aileron_R': 5, 'wing_lower_L': 56, 'wing_lower_R': 56, 'flaperon_L': 5, 'flaperon_R': 5,
          'stab_L': 12, 'stab_R': 12, 'elevator_L': 5, 'elevator_R': 5, 'fin': 8, 'rudder': 6}
FUEL_KG = 280.0
# flaperon / aileron droop (HighLiftDevice moving part = a pivot above each ControlSurface visible mesh): angle + a slotted-flap shift
DROOP_DEG = 18.0                          # lower flaperons
DROOP_DEG_UPPER = 14.0                    # upper ailerons (18 + 18 roll touched the upper cove by one triangle)
DROOP_AFT, DROOP_DOWN = 0.04, 0.02        # (round 2 HighLiftDevice shift; round 3 uses DROOP_PIVOT_BELOW)
DROOP_PIVOT_BELOW = 0.12                  # round 3: flap pivot 0.06 m below the hinge line: a 20 deg droop also moves the surface ~0.02 m aft (clears the cove)
# functional hook: the FD-32 CG is 0.10 m higher than the Mk I's (no radiator bath), so the hinge goes up 0.04 m and the stowed bar 1 deg
# lower (line of pull >= -0.50 m in the 3-point attitude, stowed bar still inside the tail cone)
# (round 3 hook (0, -1.68, 0.20) / 2.45 m / stow -0.5 replaced in round 6: HOOK_PIVOT6 below)
EYE = S.EYE


# ---------------------------------------------------------------- round 3: longer fuselage (canopy + seat room), retractable gear
STRETCH_Y = -1.02                # every vertex / pivot aft of this moves STRETCH_L aft (lower-wing TE -1.00 and the fillets stay ahead)
STRETCH_L = 0.40
# round 6 (user, 1.5.1 review: "SEMI-retractable", legs pulled BACKWARDS and tucked close to the body; docs/fd32_design.md 19):
# the v1 stance (Mk I axle (0.905, 0.70, -1.65): track 1.81 m, CoM 0.40 m aft of the axles) with a single cantilever oleo per side
# in the plane GEAR_LEG_X (inboard of the tyre), raked forward from a pivot BELOW the lower wing (behind its LE) on a trunnion mount
# webbed to the wing underside. The leg swings straight back about the lateral axis (LandingGear fold, yaw 0) by GEAR_FOLD_DEG; the
# wheel ends ~0.10 m under the lower-wing root, partly exposed (the game counts it as retracted). No barrel, no wells.
GEAR_LEG_X = 0.905 - 0.0775 - 0.058     # leg centre plane: tyre inner face (W 0.155) - leg radius - 1 cm
GEAR_PIVOT_Y = 0.34                      # round 9: 0.06 m behind the lower-wing LE (0.40); the axle moved 0.15 m forward (nimrod_spec MAIN_AXLE)
GEAR_PIVOT_BELOW = 0.075                 # pivot this far below the wing underside (inside the trunnion boss)
GEAR_MOUNT_X = (0.635, 0.700)            # lug plate (inboard of the leg) carrying the pivot boss, webbed to the wing underside
GEAR_FOLD_DEG = None                     # round 7: computed (fd32_gear6.fold_axis_angle: ~135 deg about a TILTED axis)
GEAR_STOW_BETA = 4.0                     # round 7 (in-game 1.5.2: the 92 deg wheel hung 0.7 m under the wing and read as gear down): the leg
                                         # swings aft about a tilted axis and ends lying flat along the wing-root underside, aimed this many
                                         # deg outboard of straight aft, with the wheel FLAT (axle vertical) ~0.14 m under the wing / belly
GEAR_FOLD_YAW = 0.0
GEAR_FOLD_AFT = True                     # LandingGear fold sense: the wheel goes aft (FD32Build picks the sign from the stowed position)
TAIL_FOLD_DEG = 0.0                      # round 6: FIXED tailwheel (Unity: foldDegrees 0.5, the Mk I fixed-gear value)


def main_fold_axis(x):
    """Blender fold axis of the main leg (lateral; yaw 0). A positive rotation about +X moves a hanging wheel FORWARD, so the aft
    fold is a rotation by -GEAR_FOLD_DEG (main_fold_sign)."""
    from mathutils import Vector
    return Vector((1.0, 0.0, 0.0))


def main_fold_sign():
    return -1.0 if GEAR_FOLD_AFT else 1.0


# round 6 hook (docs/fd32_design.md 19, fault 3): the hinge stays near the CG height (Mk I line-of-pull lesson) and the bar runs in a
# belly slot computed from its swept envelope (fd32_parts.hook_slot); stowed tip-down with the head in a flush recess ahead of the
# fixed tailwheel; deployed steeper so the shorter bar still reaches 6 cm below the wheel-contact plane.
HOOK_PIVOT6 = (0.0, -1.65, 0.17)         # pre-stretch (post-stretch y -2.05), 0.10 m above the CG (line of pull >= -0.50 m in the 3-point attitude)
HOOK_LEN6 = 2.36
HOOK_STOW6 = -10.0                       # deg, tip DOWN (the head lies in the belly recess)
HOOK_DEPLOY6 = -72.0


def apply_stretch():
    """after the parts are built and stretched: shift the nimrod_spec values that describe positions aft of STRETCH_Y (contract, seam
    normals, checks). Idempotent."""
    if getattr(S, '_fd32_stretched', False):
        return S
    d = STRETCH_L

    def sh(p):
        return (p[0], p[1] - d if p[1] < STRETCH_Y else p[1], p[2])
    S.TAIL_AXLE = sh(S.TAIL_AXLE); S.HOOK_PIVOT = sh(S.HOOK_PIVOT); S.SKID_PIVOT = sh(S.SKID_PIVOT)
    S.CENTRE_AFT_Y -= d
    S.COCKPIT_Y = (S.COCKPIT_Y[0] - d, S.COCKPIT_Y[1])
    S.FUS = [((r[0] - d) if r[0] < STRETCH_Y else r[0],) + tuple(r[1:]) for r in S.FUS]
    S.FIN_LE_ROOT -= d; S.FIN_HINGE -= d; S.RUDDER_TE -= d; S.STAB_LE -= d; S.STAB_HINGE -= d; S.STAB_TE -= d; S.ELEV_HINGE -= d
    import math as _m
    S.THREE_POINT_DEG = _m.degrees(_m.atan2((S.TAIL_AXLE[2] - S.TAILWHEEL_R) - S.GROUND_LEVEL_Z, S.MAIN_AXLE[1] - S.TAIL_AXLE[1]))
    S._fd32_stretched = True
    return S


def apply():
    S.PROP_R = PROP_R
    # 1.8.0 rounded cockpit opening: the Mk I generator builds the skin BEFORE the stretch, so the hole is shaped in the stretched frame
    # (pre-stretch y -> y - STRETCH_L aft of STRETCH_Y), squarer corners than the Mk I under the canopy (the stock seat's head box)
    # NOT used on the FD-32 in 1.8.0 (OPENING_ROUND False): the stretch moves everything aft of STRETCH_Y as one 0.40 m band, so a rear U
    # can only live in the last 3 cm; tried (r180 renders, fd32 checks 43/45: decking inside the eye's near plane). To be redone with the
    # canopy redesign on the stretched skin.
    S.OPENING_ROUND = False
    S.OPENING_EXP = (20.0, 4.0)        # front stays square (the eye sits 0.2 m behind the front edge: near-plane check), rear corners rounded
    S.OPENING_YMAP = lambda y: y - STRETCH_L if y < STRETCH_Y else y
    S.OPENING_Y_POST = (S.COCKPIT_Y[0] - STRETCH_L, S.COCKPIT_Y[1]) if not getattr(S, '_fd32_stretched', False) else S.COCKPIT_Y
    if not getattr(S, '_fd32_stretched', False):      # (apply() may run again after apply_stretch: never un-shift the hinge)
        S.HOOK_PIVOT = HOOK_PIVOT6
    S.HOOK_STOW_UP = HOOK_STOW6
    S.HOOK_LEN = HOOK_LEN6
    S.HOOK_DEPLOY = HOOK_DEPLOY6
    if not getattr(S, '_fd32_rudder', False):
        S.RUDDER_CHORD_TABLE = [(z, c * RUDDER_SCALE) for z, c in S.RUDDER_CHORD_TABLE]
        S.RUDDER_TE = S.FIN_HINGE - (S.FIN_HINGE - S.RUDDER_TE) * RUDDER_SCALE
        S._fd32_rudder = True
    return S
