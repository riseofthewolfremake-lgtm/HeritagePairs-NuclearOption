"""MSB-17, formerly MSB-17/80 (jsonKey MSB17, until 1.9.9 MSB1780; Heritage Pairs 1.9.0): every number of the model that differs from the B-17G.

Import this module BEFORE b17g_parts / b17g_detail / b17g_nacelle / b17g_nose1817: it patches the b17g_spec module object IN PLACE (the
GA-25X / FD-32 way: the B-17G generator is reused by import, its files stay byte-identical; tools/stub_tests_190.py checks that), so the
B-17G lines the MSB keeps (fuselage stations, tail, wing planform, nacelle bodies, main gear, tail wheel) come from the accepted B-17G code.

Blender frame as the B-17G: nose +Y, up +Z, right wing +X, metres, gear down, bay doors closed. Internal part names keep the b17g module
names where the reused code makes them (the centre fuselage object is renamed B17G -> MSB17 (KEY) in build_msb1780.py).
Design: docs/msb17_80_design.md (round 1) + the user's decisions of 2026-11-10 (tail wheel kept, custom twin 20 mm, radar 60 km, no player
auto-flares).
"""
import math
import b17g_spec as S

MSB = True
KEY = 'MSB17'        # 1.9.9: was MSB1780 (the aircraft is renamed MSB-17; repo file / folder names keep msb1780)

# ---------------------------------------------------------------- fuselage: the old radio room joins the centre section (bay 5.7 m)
S.SPLITS = [5.00, 2.90, -3.45, -8.60, -13.00]
S.FUS_PARTS = ['fus_nose', 'fus_cockpit', 'B17G', 'fus_waist', 'fus_tail', 'tail_gun']
S.RADIO_HATCH = (-99.0, -98.9)          # no radio gunner: the hatch is closed skin
# bay: 5.70 m long (y -3.40..2.30), doors 2 x 0.92 m, roof 0.75 (the wing carry-through box sits above it), hardpoint on the centre line
S.BAY_Y = (-3.40, 2.30)
S.BAY_HALF_W = 0.92
S.BAY_ROOF_Z = 0.75
S.HP_BOMBBAY = (0.0, -0.51, 0.05)
S.CATWALK_Z = (0.67, 0.72)              # no catwalk: a keel beam under the roof
S.CATWALK_HALF_W = 0.04
BAY_HP = {   # hardpoint sets in the bay (x, y, z): centre / tandem / side-by-side racks (docs/msb17_80_design.md 2.3)
    'hp_bay': (0.0, -0.51, 0.05), 'hp_bay_fwd': (0.0, 0.70, 0.30), 'hp_bay_aft': (0.0, -1.80, 0.30),
    'hp_bay_L': (-0.45, -0.70, 0.40), 'hp_bay_R': (0.45, -0.70, 0.40),
}
# stock mount envelopes (tools/msb1780/mount_envelope.py on the user's export: Unity mount frame x right, y up, z forward -> here
# (x0, x1, y0, y1, z0, z1) in the BLENDER frame relative to the hardpoint: x = x, y = Unity z, z = Unity y)
def _env(x0, x1, uy0, uy1, uz0, uz1):
    return (x0, x1, uz0, uz1, uy0, uy1)


STORES = {
    'hp_bay': {
        'bomb_500_internalx8': _env(-0.51, 0.51, -0.61, 0.32, -2.85, 2.77), 'bomb_500_internalx6': _env(-0.71, 0.71, -0.61, 0.32, -1.37, 1.36),
        'AGM_heavy_internalx8': _env(-0.55, 0.55, -0.72, 0.32, -2.55, 2.47), 'CruiseMissile1_internalx2': _env(-0.80, 0.80, -0.38, 0.33, -2.44, 1.99),
        'bomb_penetrator1_internalx4': _env(-0.49, 0.49, -0.44, 0.58, -2.32, 2.33), 'ARM1_internalx4': _env(-0.56, 0.56, -0.43, 0.60, -2.24, 2.21),
        'bomb_500_glide_internalx6': _env(-0.82, 0.82, -0.53, 0.58, -2.04, 2.03), 'AShM2_internalx8': _env(-0.70, 0.70, -0.64, 0.63, -1.90, 1.89),
        'nuclearBomb1_internalx4_stack': _env(-0.43, 0.43, -0.18, 0.61, -2.02, 1.58), 'nuclearBomb1_strategic_internalx4_stack': _env(-0.43, 0.43, -0.18, 0.61, -2.02, 1.58),
        'AAM4_triple_internal': _env(-0.49, 0.49, -0.24, 0.04, -1.70, 2.14),
    },
    'hp_bay_fwd': {'bomb_250_internalx8': _env(-0.74, 0.74, -0.46, 0.18, -1.14, 1.11), 'bomb_250_glide_internalx8': _env(-0.74, 0.74, -0.54, 0.20, -1.14, 1.11)},
    'hp_bay_aft': {'bomb_250_internalx8': _env(-0.74, 0.74, -0.46, 0.18, -1.14, 1.11), 'bomb_250_glide_internalx8': _env(-0.74, 0.74, -0.54, 0.20, -1.14, 1.11)},
    'hp_bay_L': {'bomb_glide1_six_inernal': _env(-0.42, 0.42, -0.30, -0.02, -1.65, 2.05), 'bomb_125_internalx6': _env(-0.43, 0.43, -0.22, 0.00, -1.53, 1.93)},
    'hp_bay_R': {'bomb_glide1_six_inernal': _env(-0.42, 0.42, -0.30, -0.02, -1.65, 2.05), 'bomb_125_internalx6': _env(-0.43, 0.43, -0.22, 0.00, -1.53, 1.93)},
}
S.STORES = {k: v for k, v in STORES['hp_bay'].items()}     # the B-17G bay check reads S.STORES against S.HP_BOMBBAY

# defensive side bays (MMR-S3 x2 each, AAM1_double_internal: Unity w 0.65 h 0.35 l 2.87 m), lower fuselage sides behind the wing:
# hardpoint rolled 90 deg outboard (the mount's 'down' = outboard: the missiles leave sideways), door on the side skin
SIDE_BAY = dict(y=(-7.95, -5.05), z=(0.02, 0.80), hp_x=0.50, hp_y=-6.635, hp_z=0.45, liner_x=0.46, env=_env(-0.33, 0.33, -0.32, 0.03, -1.30, 1.57))
# waist sensor windows (missile-warning / IR sensor windows above the side bays; the waist gunners are gone)
SENSOR_WIN = dict(y=(-6.25, -5.70), z=(0.92, 1.18))
S.WAIST_R = S.WAIST_L = (SIDE_BAY['y'][0], SIDE_BAY['y'][1])     # station rows on the side-bay door edges; frames clear of the bays
S.WAIST_Z = (-0.20, 1.45)

# ---------------------------------------------------------------- crew escape hatches (jettisoned Canopy panels; stock ejection seats)
EWO_HATCH = dict(y=(2.62, 2.93), x=(-0.02, 0.60))       # roof over the EWO (B17G centre section, right of the dorsal laser race r 0.60)
PILOT_HATCH_Y = (3.25, 3.85)                           # the B-17 overhead windows become the pilots' glazed escape hatches
NOSE_HATCH = (5.80, 6.33, -0.30, 0.30)                 # WSO: the nose top window enlarged into a glazed hatch (y0, y1, x0, x1)
for _w in S.NOSE1817_WINDOWS:
    if _w.get('tag') == 'top_win':
        _w['rect'] = NOSE_HATCH
        _w['rc'] = 0.06
S.NOSE1817_K5 = []                                     # no cheek guns: the K-5 frames and their gun sockets are gone
S.NOSE1817_MAST = None

# ---------------------------------------------------------------- defensive positions (laser / 20 mm turrets on the B-17G turret stations)
# chin: remote twin 20 mm on the Bendix position (the exact 0.50 m chin opening of the 1.8.17 nose); tail: remote twin 20 mm in the
# Cheyenne opening; 'top' = the dorsal 120 kW laser in the top-turret roof opening; 'ball' = the ventral laser, moved 0.40 m aft
# (y -4.35) clear of the longer bay (ends at -3.40). Internal keys kept so the reused B-17G race / opening code still finds them.
TWIN_DX = 0.130                                        # barrel half spacing of the twin 20 mm (barrel axes +-0.15 m from the cradle centre)
S.TURRETS = {
    'chin': dict(pos=(0.0, 6.14, -0.74), fwd=(0, 1, 0), guns=[(-TWIN_DX, 0.0), (TWIN_DX, 0.0)], station='Chin', trav=90.0, emin=-60.0, emax=15.0),
    'top': dict(pos=(0.0, 2.08, 2.12), fwd=(0, 1, 0), guns=[(0.0, 0.0)], station='Dorsal', trav=360.0, emin=0.0, emax=90.0),
    'ball': dict(pos=(0.0, -4.35, -0.80), fwd=(0, 1, 0), guns=[(0.0, 0.0)], station='Ventral', trav=360.0, emin=-90.0, emax=0.0),
    'tail': dict(pos=(0.0, -14.70, S.TAIL_GUN_Z), fwd=(0, -1, 0), guns=[(-TWIN_DX, 0.0), (TWIN_DX, 0.0)], station='Tail', trav=30.0, emin=-40.0, emax=40.0),
}
LASERS = ('top', 'ball')
GUNS20 = ('chin', 'tail')
BALL_HOLE_R = 0.72                                     # ventral laser opening = the B-17G ball's (face-wise cut: the band / flange cover its edge)

# ---------------------------------------------------------------- engines: 4 x 4.03 MW turboshaft, two contra-rotating 6-blade rows each
S.PROP_R = 1.70
S.PROP_BLADES = 6
ROW_GAP = 0.50                                         # aft row -> front row along the axis
AFT_ROW_DY = 0.70                                      # aft row plane ahead of the B-17G cowl lip (ylip + 0.70)
COWL = dict(r_spin=0.40, y_spin=0.50)                  # cowl nose: tapers from the lip ring (R 0.78 / 0.77) to the spinner base r 0.40 at ylip + 0.50
ROW_TURN = {'front': 1, 'aft': -1}                     # ConstantSpeedProp.turnDirection per row (contra pair: the torques cancel on every engine)
S.PROP_TURN = {1: 1, 2: 1, 3: 1, 4: 1}                 # (the front rows; b17g_detail.build_props is not used)


def prop_planes(kind):
    """(aft row y, front row y, spinner tip y) of an engine."""
    xa, za, ylip, yprop, R, yend, zb = S.NACELLES[kind]
    ya = ylip + AFT_ROW_DY
    return ya, ya + ROW_GAP, ya + ROW_GAP + 0.62


# ---------------------------------------------------------------- pylons (outboard of the outer prop discs, |x| 9.3 / 11.8)
PYLONS = {'inner': 9.30, 'outer': 11.80}
PYLON_DROP = 0.32                                      # pylon height under the wing lower skin
PYLON_LEN = {'inner': 2.10, 'outer': 1.70}

# ---------------------------------------------------------------- cockpit / crew
FLOOR_Z = 0.40                                         # flight-deck floor (B-17G)
EYE_PILOT = (-0.38, 3.45, 1.70)                         # 0.13 m ahead of the B-17G eye: the seat rises through the overhead hatch (3.25-3.85)
EYE_COPILOT = (0.38, 3.45, 1.70)
EYE_WSO = (0.0, 6.00, 1.10)                            # nose tactical station (the bombardier position)
EYE_EWO = (0.20, 2.78, 1.68)                           # behind the co-pilot, facing outboard right to the EW console, under its hatch
NOSE_FLOOR_Z = 0.10                                    # 1.9.1: the stock seat's base sits ~0.97 m and the feet ~1.0 m under the eye (EW-25 figure): one floor level
                                                       # (1.9.0's 0.34 left the seat base and feet through the floor)

# ---------------------------------------------------------------- 1.9.1 flight deck: the stock EW-25 two-pilot glass cockpit (kitbash-stock-parts)
# The EW-25 seats its pilots side by side at x +-0.40 like ours (+-0.38). Its parts are placed by the EW-25 helmet camera point -> our pilot eye:
# blender = (ux, uz + EYE_PILOT.y - EW1_HELMET.z, uy + EYE_PILOT.z - EW1_HELMET.y) for a node at EW-25 prefab position (ux, uy, uz).
# Read from the user's own export at study time (prefab EW1, nodes cockpit_F/...): positions only; the meshes stay in the game files.
STOCK_DECK = True                                      # 1.9.1-1.9.4; 1.9.5: False (DECK195 below), kept as the documented fallback
EW1_HELMET = (-0.367, 1.171, 7.418)                     # EW1 .../pilot/.../head/helmetCamPoint (Unity, prefab space)
EW1_FLOOR_U = 0.10                                     # EW1_cockpit_int lowest point (local y -0.547 + node y 0.648)
STOCK_KIT = [   # (our name, stock mesh, template node 'EW1:<node>', EW-25 prefab position, cockpit-layer copy)
    ('cockpit_ew1_tub', 'EW1_cockpit_int', 'EW1:cockpit_F_int', (0.0, 0.648, 7.71)),
    ('cockpit_ew1_tacscreen', 'EW1_targetScreen', 'EW1:targetScreen', (0.0, 0.648, 7.71)),
    ('stick_L', 'EW1_joystick', 'EW1:joystick_L', (-0.438, 0.097, 8.056)),
    ('stick_R', 'EW1_joystick', 'EW1:joystick_R', (0.438, 0.097, 8.056)),
    ('cockpit_throttle', 'EW1_throttle', 'EW1:throttle', (0.0, 0.518, 8.104)),
]
STOCK_TUB_BOX = ((-1.023, 1.023), (2.944, 4.731), (0.63, 1.785))   # blender bounds of the placed tub (measured, try_ew1 study)


EYE_PILOT_191 = EYE_PILOT                                # the 1.9.1 placement frame (DECK_Z, STOCK_TUB_BOX and the EWO station were sized on it)


def stock_pos(u):
    return (u[0], u[2] + EYE_PILOT_191[1] - EW1_HELMET[2], u[1] + EYE_PILOT_191[2] - EW1_HELMET[1])


DECK_Z = stock_pos((0.0, EW1_FLOOR_U, 0.0))[2]          # the tub floor in our frame (0.629): the EWO platform continues it aft

# ---------------------------------------------------------------- 1.9.5 flight deck: OUR OWN deck with single stock parts (user order 2026-11-10:
# "Rebuild a custom cockpit using stock parts"; memory kitbash-stock-parts: no whole stock cockpit). blender/msb1780/msb_deck195.py builds the
# panel / glare shield / pedestal / consoles / floor / walls; Unity puts the stock parts on the anchors below. Placement facts (the user's
# AssetRipper export, read at study time; positions only):
#   SFB-81 (prefab Darkreach, the game's two-pilot side-by-side heavy bomber): Pilot / WSO roots at x -+0.494, joystick_L / _R = root +
#   (-+0.042, -0.3926, +0.4555) (Unity x, y up, z fwd), the ONE centre throttle quadrant (two levers at x -+0.09) = Pilot root + (0.494, -0.1705,
#   +0.4579); Cockpit.joysticks range 12, Cockpit.throttles range 52 (rotation). Our figures are the COIN figures (GA-25X / 1.9.0 crew):
#   figure root = helmet eye + (0, -0.7147, +0.0651) (Unity), so the SFB offsets are applied to OUR figure root (the GA-25X 0.3.1 method).
#   EW-25 (EW1, two-pilot): warningLights (mesh EW1_warningLights, material CockpitWarningLight, driven by the stock CockpitWarningLights:
#   blinks on a missile warning) - one 3 cm lamp; its lamp centre is mesh-local (0, 0.4145, 0.5485) (Unity).
STOCK_DECK = False
DECK195 = True
DETAIL196 = True          # 1.9.6 detail pass on our deck (blender/msb1780/msb_detail196.py); False = the 1.9.5 deck
# 1.9.7 (user on 1.9.6): three model fixes, each behind its flag (False = the 1.9.6 model)
TAIL_PLATED197 = True     # no human tail gunner: every window of the B-17G tail cab (side panes, small forward windows, the sloped aft face)
                          # is closed skin (paint, double skin, panel lines from the texture builder) and the cab's frame bars are gone
SMOOTH197 = True          # curved surfaces built with their own vertices (doors / hatches taken out of the skin, rings) get smooth custom
                          # normals shared with the skin round them (blender/msb1780/msb_smooth197.py)
QUADRANT197 = True        # throttle quadrant: the console top rises round the stock levers (top radius QUAD_TOP_R about the stock pivot)
                          # with two slots, so each lever arm stands IN its gate from idle to full (1.9.6: the arm's cut end hung 12-15 mm
                          # above the gate surface)
QUAD_TOP_R = 0.205        # quadrant top radius about the stock throttle pivot (sfb_throttle: arm foot r 0.178-0.190, knob from r 0.260)
QUAD_SLOT_X = (0.079, 0.095)   # slot |x| (the arm is |x| 0.083-0.091; the knob, |x| 0.075-0.099, is wider than the slot)
QUAD_SLOT_K = (5, 21)     # slot along the gate arc, indices of the 25 arc stations: -55.9 .. +14.8 deg (arm foot -50.5 at idle .. +8.8 at full)
FIG_ROOT = (0.0, 0.0651, -0.7147)                     # our (COIN) figure root - helmet eye, BLENDER frame (x, y fwd, z up)
SFB_STICK = (0.042, 0.4555, -0.3926)                  # SFB-81 joystick - its figure root, Blender frame (x outboard: sign of the seat side)
SFB_THROTTLE_Y, SFB_THROTTLE_Z = 0.4579, -0.1705      # SFB-81 throttle - its Pilot root (x: the deck centre line)
SFB_THROTTLE_RANGE = 52.0                             # Darkreach Cockpit.throttles range (rotation)
SFB_STICK_RANGE = 12.0                                # Darkreach Cockpit.joysticks range
EW1_LAMP_LOCAL = (0.0, 0.5485, 0.4145)                # EW1_warningLights lamp centre in its mesh frame, Blender (x, y fwd, z up)
# 1.9.5 crew moves (the seat-clearance check t2 on the stock ejection seats where the figures put them; pre-existing since 1.9.0 / 1.9.1):
#   pilots: the EWO seat's back top crossed the pilot seat's back top (x -0.30..-0.22, y 2.96-3.01, z 1.59-1.80) and each pilot seat's
#   outboard rail top poked 3 cm through the roof skin at (+-0.52, 3.21, 1.97) -> pilot eyes 0.11 m forward and 0.04 m down (the seat
#   columns still rise through the 3.25-3.85 hatches, check s); the EWO (hatch 2.62-2.93, laser race) cannot move.
#   WSO: the seat base sat 2.7 cm under the 0.10 floor and through the seat base -> WSO eye 0.035 m up (seat on a thin plate).
if DECK195:
    EYE_PILOT = (-0.38, 3.56, 1.66)
    EYE_COPILOT = (0.38, 3.56, 1.66)
    EYE_WSO = (0.0, 6.00, 1.135)


def stick_anchor(side):
    e = EYE_PILOT if side < 0 else EYE_COPILOT
    return (e[0] + side * SFB_STICK[0], e[1] + FIG_ROOT[1] + SFB_STICK[1], e[2] + FIG_ROOT[2] + SFB_STICK[2])


def throttle_anchor():
    return (0.0, EYE_PILOT[1] + FIG_ROOT[1] + SFB_THROTTLE_Y, EYE_PILOT[2] + FIG_ROOT[2] + SFB_THROTTLE_Z)

# ---------------------------------------------------------------- 1.9.12 (user): visible airbrake panels + the green formation-light strips
# Each behind its flag (False = the 1.9.11 model: no object, no contract key). Geometry: blender/msb1780/msb_ext1912.py (plates cut from the
# uncut skin and lifted along its normals; the owning parts' meshes, colliders and the livery atlas stay as in 1.9.11).
SPOILERS1912 = True       # six upper-wing spoiler panels ahead of the flaps (docs/msb17_80_design.md: "the spoiler panels become airbrakes"),
                          # driven by the stock Airbrake the MSB has had since 1.9.2 (Unity: AirbrakePanels1912)
# round 2 (review of the first build: 0.9 / 1.4 m tabs of 13 % chord were too small for a 31 m wing and dragAmount 3.0): three pairs, each as
# long as its bay allows, 18.5 % chord. Free room MEASURED on the built model (model check row x2):
#   in   |x| 1.40-2.70  between the fuselage side (1.165) and the inner nacelle's upper fairing (which runs back to about 65 % chord at 3.0-3.15)
#   mid  |x| 4.97-6.88  from 0.21 m outboard of the wing split 4.75 (bed rim) to 0.31 m inboard of the outer exhaust line 7.20; the outer nacelle's tail
#                       ends at about 46 % chord, so the panel passes BEHIND it (front edge at 52 %)
#   out  |x| 7.52-8.68  from 0.31 m outboard of the exhaust line 7.20 to 0.21 m inboard of the wing split 8.90 (flap end 8.80); the
#                       10 mm bed rim counts (model check x2 measures the bed's vertices too)
# Nothing fits between the inner exhaust line 3.83 (+0.30) and the split 4.75 (-0.20): 0.42 m. No panel ahead of the ailerons (8.95-14.74).
SPOILER_X = {'in': (1.40, 2.70), 'mid': (4.97, 6.88), 'out': (7.52, 8.68)}
SPOILER_PART = {'in': 'wing_inner_', 'mid': 'wing_mid_', 'out': 'wing_mid_'}
SPOILER_S_FRONT = 0.52    # hinge line chord fraction (first build: the ring row 0.5714)
SPOILER_S_REAR = 0.705    # rear edge chord fraction (flap cove / hinge at 0.735)
SPOILER_MAX_ANGLE = 55.0  # deg, opens upward about the front edge (supervisor: 50-60)
SPOILER_TOP, SPOILER_BOTTOM = 0.015, 0.009       # panel top / underside above the skin (m)
SPOILER_BED_TOP, SPOILER_BED_BOTTOM = 0.004, 0.002   # dark bed plate: top 4 mm above the skin; its back face 2 mm above the skin, facing it (a closed slab,
                          # not embedded: the wing's inner skin lies 2-6 mm under the outer one and an embedded back face z-fought with it).
                          # Round 2: 3 / 1 mm measured 0.60 mm from the built skin triangles at the closest vertex (model check z2); now >= 0.8 mm everywhere
SPOILER_RIM = 0.010       # the bed is this much larger than the panel all round: the seam line of the shut panel
# round 2: the bed reads as a recess with structure, the panel underside as a stiffened skin (the first build: two flat plates)
SPOILER_BEDRIB_TOP, SPOILER_BEDRIB_BACK = 0.0075, 0.003   # frame / ribs / stringer on the bed (material gear): top 3.5 mm above the bed top, back face inside the bed slab
SPOILER_BEDRIB_W = 0.035      # width of the bed's frame, ribs and stringer
SPOILER_BED_FRAME_IN = 0.005  # the frame's outer edge lies this far INSIDE the panel outline (hidden when shut: the seam stays dark)
SPOILER_BED_STRINGER = 0.55   # the bed's spanwise stringer at this fraction of the panel chord behind the hinge line
SPOILER_PRIB_TOP, SPOILER_PRIB_BOTTOM = 0.012, 0.0052     # stiffeners under the panel (material gear): top inside the panel's thickness, bottom 1.2 mm above the bed top when shut
SPOILER_PRIB_W = 0.030
SPOILER_PRIB_INSET = 0.07     # the stiffeners start / end this far from the hinge line and the rear edge
SPOILER_BAY = 0.33            # rib pitch aimed at (bed ribs at k / n of the span, panel stiffeners and hinge arms at the half stations between them)
SPOILER_ARM_W, SPOILER_ARM_DEPTH = 0.024, 0.11
STRIPS1912 = True         # eight green formation-light strips (study light_strips.md + check_light-strips.md; Unity: FormationLights1912)
STRIP_FWD = dict(y=(3.20, 4.40), z=(1.10, 1.20))     # fus_cockpit, under the side windows (sill 1.31, frame bar from 1.27), above the outer nacelle top line 1.07
STRIP_AFT = dict(y=(-7.85, -6.55), z=(1.05, 1.15))   # fus_waist, above the side-bay doors (hinge 0.835), aft of the sensor windows, ahead of the roundel
STRIP_FIN = dict(z=(3.70, 4.90), behind_le=(0.25, 0.35))   # both faces of the fin, parallel to the leading edge, above the serial (to z 3.20)
STRIP_TIP = dict(x=(14.99, 15.11), chord=(0.15, 0.55))     # wing_tip top, outboard of the aileron end (14.74) and the wing roundel (to 13.7)
STRIP_LIFT, STRIP_BACK = 0.005, 0.002            # front face / back face above the skin (closed slab; the back face looks at the skin, 2 mm off it;
                          # round 2: 4 / 1 mm measured 0.72 mm from the built skin triangles at the closest vertex, model check z2)

import os as _os
if _os.environ.get('MSB1912_OFF') == '1':     # regression build only (flags off must give the 1.9.11 model): MSB1912_OFF=1 blender ... build_msb1780.py
    SPOILERS1912 = STRIPS1912 = False

# ---------------------------------------------------------------- budgets
S.TRI_BUDGET_TOTAL = 245000
