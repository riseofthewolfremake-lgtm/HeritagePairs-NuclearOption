"""GA-25X 0.3.2 cockpit: reference-standard rebuild (offline worker, 2026-11-01).

0.3.1 (stock-part kitbash with two big flush displays) was rejected: "buttons are missing, dials are missing", throttles float,
pedals angled backwards. 0.3.2 follows what the reference cockpits are made of (study: MODLOG 2026-11-01 "0.3.2 cockpit study"):
  * dense TEXTURED panels: every panel face carries panel art (our own fal-generated art, atlas ga25x_ckart_b/_n, layout
    ga25x_ckart_layout.py) on a plate with depth; a few modelled toggles / knobs / guards stand on top for relief
    (OA-27 / MC-260 pattern: modelled shapes + baked switch art; ours: art + thin relief parts);
  * displays set INTO bezels with push-button rows (bezel art with the opening cut out, display face recessed behind);
  * glareshield with an annunciator row under its lip and two caution lights on top;
  * side consoles (sloped wall panels outboard of the legs) + circuit-breaker panels on the walls beside the seats;
  * a centre pedestal whose throttle quadrant is an ARC housing concentric with the stock throttle pivot: the stock
    sfb_throttle grip (which has no stalk of its own) slides 4 mm above it over its whole 0..52 deg travel, with our own
    stalk (child object cockpit_throttle_arm, rotates with the lever) coming out of the slot;
  * footwells deepened to the stock crew figure's feet (COIN pilot/WSO bone pose: heel ~0.52 m under the figure root);
    rudder pedals under the ball of each foot, face normal aft-and-up (foot presses forward), on a yaw bar standing on the floor;
  * stick bases on mount boots standing on the footwell floor.
Stock parts kept (generator, unchanged contracts): crew figures with their stock EjectionSeat, SFB-81 sfb_joystick on stick_L/R,
sfb_throttle on cockpit_throttle (EMPTIES here), the HUD (gunsight_pilot + combiner).
Materials: ck_struct (stock aircraft_structure via generator), ck_panel (plain dark grey), ck_black, ck_art (panel art atlas,
own UVs on the livery layer), screen, gauges.
Same conventions as the B-25H builders: MeshBuf in WORLD coordinates (Blender: nose +Y, up +Z, right wing +X, metres).
"""
import math, os
from mathutils import Vector, Quaternion, Matrix
import b25h_spec as S
from b25h_geom import V, MeshBuf, fan_cap, oriented_quad, cylinder, box, frame_from_axes
import ga25x_ckart_layout as LY

UP = V((0, 0, 1))
X_ = V((1, 0, 0))
Y_ = V((0, 1, 0))
LIP = 0.002              # bezel lip over the display face edge (m)
DISPLAY_RECESS = 0.004   # display face behind the bezel art face (m)
BULKHEAD_Y = 2.685       # capsule rear bulkhead (fus_cockpit starts at 2.62)
FOOTWELL_Y = 4.42        # footwell front wall (under the panel)
STEP_Y_OUT = 3.83        # seat deck -> footwell step, |x| >= 0.30 (outboard of the nose-wheel well)
STEP_Y_IN = 3.95         # same, CENTRE_HALF_X <= |x| < 0.30 (nose-wheel well top z 0.06 runs to y 3.95)
WELL_PLATE_Z = 0.062     # 0.3.2: thin plate over the nose-wheel well top between STEP_Y_OUT and STEP_Y_IN (the inner shins pass
                         # 7 mm above it; the 0.3.1 deck-height strip there cut the shins)
WELL_CHAMFER = (3.87, -0.09)  # 0.3.2: nose-wheel well top-front corner chamfered from (y 3.87, z 0.06) to (y 3.95, z -0.09)
                              # (build_ga25x.py well profile) so the stock figures' inner shins pass in front of it
WELL_HALF_X = 0.30
CENTRE_HALF_X = 0.102    # centre cover strip over the 76 mm breech (0.3.2: breech +-0.10) stays at deck height; the stock
                         # figures' inner feet stand at |x| >= 0.125 beside it
CENTRE_FWD_HALF_X = 0.101  # ahead of the breech (BREECH_END_Y) the strip narrows over the 0.095 m recoil sleeve
BREECH_END_Y = 3.95       # (0.3.2 final: breech 0.19 m wide -> the narrow strip runs the whole footwell length)
WALL_X = 0.690           # side wall inner face (fuselage half width 0.725)
SILL_Z = 0.865
FOOT_Z = -0.200          # 0.3.2 footwell floor: the stock figure's heel (COIN bone pose) rests here

# stock placement (Blender frame: x, y fwd, z up) -- measured from the stock prefabs (MODLOG 0.3.1 / 0.3.2)
FIG_EYE_TO_ROOT = V((0.0, 0.0651, -0.7147))
STICK_FROM_ROOT = (0.042, 0.4555, -0.3926)          # x sign: outboard
THROTTLE_FROM_ROOT = (0.4579, -0.1705)               # (fwd, up) from the pilot figure root, SFB-81
THROTTLE_EXTRA_FWD = 0.219                           # clears the stock seat's inner front edge
SLOT_A0, SLOT_A1 = -54.0, 13.0                       # 0.3.3 slot opening along the arc (deg from up, + fwd): lever -46 .. +6 deg +- margin
SLOT_HX, SLOT_DEPTH = 0.025, 0.030                   # slot half width (lever outer edge 0.0205 -> 4.5 mm gap), depth
LEVER_DEG, LEVER_X, LEVER_W, LEVER_T, LEVER_R = -46.0, 0.0125, 0.016, 0.010, 0.215   # split lever halves (pivot frame)
HEAD_W = 0.022
ART_DEG = (-81.0, 32.0)                              # throttle gate art v=0..1 along the arc (IDLE at -46, MAX at +6 deg)
THROTTLE_DROP = 0.060                                # 0.3.2: at full throttle (52 deg) the stock grip top (r 0.341 m) cleared the
                                                     # panel bottom (z 0.465) by -4 cm (into it); 6 cm lower it clears by 2 cm
STICK_RANGE = 12.0
THROTTLE_RANGE = 52.0
# COIN_PLACEHOLDER.prefab crew figure bones relative to the figure root (Unity x, y up, z fwd -> here (x, fwd, up)), default
# (seated) pose; L = figure's left (-x). Read with a YAML forward-kinematics pass (study tool, not in the repo).
LEG_BONES = {'hip': (0.0917, 0.0048, -0.0235), 'knee': (0.1418, 0.4044, -0.0378), 'ankle': (0.1722, 0.5485, -0.4480),
             'toe': (0.2090, 0.7623, -0.3900)}
# sitting crew leg envelope used by the generator and the offline check (approximation: capsules around the bones; foot =
# box from heel to toe tip whose sole lies SOLE_BELOW_ANKLE under the ankle bone and SOLE_BELOW_TOE under the toe-end bone)
THIGH_R, SHIN_R, FOOT_HALF_W = 0.075, 0.055, 0.045
SOLE_BELOW_ANKLE, SOLE_BELOW_TOE, HEEL_BACK = 0.080, 0.045, 0.060

# instrument panel layout (panel plane: C3.panel_pt(x, z))
MAIN_W, MAIN_H, MAIN_X, MAIN_Z = 0.440, 0.240, 0.330, 0.708      # main displays (one per crew), inside the bezel art
AUX_W, AUX_H, AUX_X, AUX_Z = 0.150, 0.070, 0.540, 0.500          # small aux panes outboard under the main displays
PANEL_BOTTOM, PANEL_TOP = 0.455, 0.952
GZ, LIP_Y = 0.955, 4.19                                            # glareshield top, aft lip


def figure_root(key):
    return V(S.CREW[key]['eye']) + FIG_EYE_TO_ROOT


def floor_z():
    from b25h_v3 import FLOOR_Z
    return FLOOR_Z


def footwell_z():
    """stock stick base height (SFB-81 relation to the crew figure); 0.3.2: the stick stands on a mount boot above FOOT_Z."""
    return figure_root('pilot').z + STICK_FROM_ROOT[2]


def leg_points(key, side):
    """world points of one leg of crew `key` (side -1 = figure's left = -x). Returns dict hip/knee/ankle/toe + heel/sole_toe."""
    r = figure_root(key)
    out = {}
    for k, (x, f, u) in LEG_BONES.items():
        out[k] = V((r.x + side * x, r.y + f, r.z + u))
    out['heel'] = out['ankle'] + V((0, -HEEL_BACK, -SOLE_BELOW_ANKLE))
    out['sole_toe'] = out['toe'] + V((0, 0.03, -SOLE_BELOW_TOE))
    return out


# 1.9.14: painted knobs / toggles on subpanel_strip.png, measured on the art (u right, v up, knob radius in strip heights).
# In game 1.9.13 the modelled ones sat beside the painted ones (user report: "textures don't match the model").
SUB_KNOBS = [(0.094, 0.473, 0.132),      # HUD MODE (round 7: was 0.490 / 0.140, see SUB_KNOB_LOW)
             (0.1817, 0.305, 0.078),     # HUD BRT (round 7: was 0.180 / 0.335 / 0.090, 30 px above the painted knob)
             (0.276, 0.667, 0.070),      # MFD BRT upper
             (0.276, 0.335, 0.070),      # MFD BRT lower
             (0.359, 0.505, 0.077)]      # ALT baro
# 1.9.14 round 7 (in-game review: the HUD MODE knob hid the inner ends of its OFF / NAV / A-A / A-G ticks and crowded "A-G").
# Measured on subpanel_strip.png: the five tick marks lie on a circle centred (389, 551) px, r 157-181 px; the painted knob dome
# + white pointer bar reach 132 px from (389, 540). The round-6 knob (centre (388, 522), r 143 px, 9 mm proud) touched the tick
# ends even head-on. Now centred on the dome, r 135 px (pointer bar covered, 13 px clear of the ticks), a low tapered disc.
# HUD BRT: the painted knurled knob is centred (750, 712) px, r ~80 px, inside its white OFF-BRT arc (circle fit (753, 706),
# r 98-132 px); the round-6 knob sat at (743, 681) r 92 px, 9 mm proud, over the arc's top: the check measured 23-52 % of the
# arc's text pixels hidden from the eye that uses each copy. Now on the painted knob, r 80 px, low.
# index -> (height on the main strip, height on the outboard column crop, top radius ratio, pointer stub height)
SUB_KNOB_LOW = {0: (0.004, 0.003, 0.80, 0.001), 1: (0.004, 0.003, 0.80, 0.001)}
SUB_TOGGLES = [(0.5189, 0.4961), (0.5870, 0.4971), (0.6839, 0.4971)]   # LDG LT, TAXI LT, STBY INST (nut centre, round 6: measured by paint_out_levers1914.py)

# 1.9.14 round 4: painted controls on the side-console and radio art, measured on the fal art (console_left.png /
# console_right.png 2528 x 1696, pedestal.png radio crop (0, 1240, 1696, 2528); u right, v up, 0-1 over the WHOLE panel art).
# Toggles = centre of the painted bezel ring (the lever pivot), knobs = knob axis, guards = centre of the striped cover,
# rockers = paddle centre, flap lever = handle centre. Read off zoomed crops with a 4 mm circle drawn on the candidate
# (study: nuclearoption-ref\study\tex_1914\ga25x_cockpit\r4\verify.py). 1.9.13 / 1.9.14 r3 put the modelled controls on a
# made-up grid 8-30 mm beside these (user: "textures clearly do not match the underlying model").
# kind: 'dn' / 'up' toggle with the MODELLED lever pointing down / up the panel (round 6: the painted levers are painted out of
# the art; before round 6 this was the painted lever's direction), ('guard', (u0, v0, u1, v1)) guarded toggle whose
# lid carries the painted striped cover (that sub-rect of the art, measured), ('knob', r m),
# ('cap', du, dv, height m, sunk m): a raised cap the size of the painted one (du x dv of panel u / v, centred on (u, v)) whose
# top shows that crop of the art (rocker paddles, push-buttons, keypad keys, the flap handle).
# Round 5 (verifier findings on round 4): the 18 mm toggle levers stood ~23 mm proud and, seen from the near crew eye ~60 deg off
# the panel normal, lay across the painted ON / OFF labels; the plain black 6 mm rocker paddles hid the ON / STBY / OFF labels and
# the painted rocker shading; the 16 mm guard lids showed a black cheek and the stripes twice. Now: short low levers, art-topped
# caps 3-4 mm proud, closed 3.5 mm lids with striped sides. ENG START L / R and the 12 keypad keys (painted only) get caps too.
_ROCKER = ('cap', 0.0336, 0.1651, 0.0035, 0.001)           # painted paddle 85 x 280 px of 2528 x 1696 (9.2 x 33.6 mm)
_KEY = ('cap', 0.0566, 0.0784, 0.0030, 0.0015)             # painted key cap 143 x 133 px (15.4 x 16.0 mm)
_ENG = ('cap', 0.0633, 0.0955, 0.0035, 0.001)              # painted ENG START cap 160 x 162 px (17.3 x 19.5 mm)
# Round 6b (verifier on round 6): the APU / NAV LT / FORM LT knobs (r 9 / 8 mm, 12 mm proud) hid 26-43 % of their painted
# OFF-BRT scale arcs from the pilot eye (a point h proud shows 1.2-1.7 h further along art +u). Measured on the raw art
# (0.108 mm / px): scale arc inner radius APU 82 px (8.9 mm), NAV / FORM 88-92 px (9.5-9.9 mm); painted pointer line of
# NAV / FORM out to 65 px (7.0 mm); painted knob skirt ~75-80 px. Knobs now low tapered discs: NAV / FORM r 7.5 mm (covers the
# painted pointer) to 0.76 r at 3 mm proud, pointer stub 1 mm; APU r 7 mm (the painted skirt shows round it as a rim, like
# CHNL / FREQ) to 0.70 r at 2.5 mm. Kind: ('knob', r, h, top ratio, pointer height).
_LT_KNOB = ('knob', 0.0075, 0.0030, 0.76, 0.001)
_APU_KNOB = ('knob', 0.0070, 0.0025, 0.70, 0.001)
CONSOLE_CTRLS = {
    'console_left': [('MASTER ARM', ('guard', (0.155, 0.684, 0.199, 0.857)), 0.177, 0.770), ('GEAR', 'dn', 0.5000, 0.7759),
                     ('FLAPS', ('cap', 0.0366, 0.0785, 0.008, 0.001), 0.8135, 0.720),
                     ('FUEL PUMP L', 'up', 0.1626, 0.4923), ('FUEL PUMP R', 'up', 0.3311, 0.4923), ('X-FEED', 'up', 0.5000, 0.4923),
                     ('ANTI-SKID', 'up', 0.6693, 0.4923), ('NWS', 'up', 0.8378, 0.4923),
                     ('ENG START L', _ENG, 0.1206, 0.1751), ('ENG START R', _ENG, 0.2255, 0.1751),
                     ('IGN', 'up', 0.3224, 0.1757), ('APU', _APU_KNOB, 0.423, 0.174), ('NAV LT', _LT_KNOB, 0.5645, 0.185),
                     ('FORM LT', _LT_KNOB, 0.690, 0.190), ('DE-ICE', 'up', 0.8054, 0.1757), ('BATT', 'up', 0.8948, 0.1757)],
    'console_right': [('LASER ARM', ('guard', (0.1565, 0.2436, 0.230, 0.364)), 0.193, 0.304), ('CHAFF', ('knob', 0.0075), 0.761, 0.795), ('FLARE', ('knob', 0.0075), 0.8845, 0.795),
                      ('TGP PWR', _ROCKER, 0.585, 0.500), ('RADAR', _ROCKER, 0.6875, 0.500),
                      ('ECM', _ROCKER, 0.7875, 0.500), ('IFF', _ROCKER, 0.8925, 0.500),
                      ('RDR MODE', ('knob', 0.0095), 0.590, 0.197), ('CHNL', ('knob', 0.0065, 0.0035), 0.750, 0.197), ('FREQ', ('knob', 0.0065, 0.0035), 0.8825, 0.197)]
                     + [(f'KEY {k}', _KEY, u, v) for k, (u, v) in zip(('1', '2', '3', '4', '5', '6', '7', '8', '9', '0', 'CLR', 'ENT'),
                                                                   [(u, v) for v in (0.8753, 0.7686, 0.6630, 0.5569) for u in (0.1675, 0.2403, 0.3129)])],
}
# toggle levers (round 5): boss r / height, lever tip height above the art face and its offset along the painted lever direction.
# The painted levers reach ~10 mm (console) / ~8 mm (radio) from the pivot; a tall lever seen ~60 deg off the panel normal lies
# across the labels beside it, so the lever is short and low. Radio: the lever stands nearly straight out: seen from either crew
# eye (44 deg off the normal, from above) its image falls on the painted lever, above the painted lower label.
# Round 6: the painted levers are painted OUT of the art (blender/ga25x/textures/paint_out_levers1914.py: the art keeps the bezel,
# the lever is the model only), and the toggle positions are the bezel centres measured there (console_left, radio, sub strip;
# <= 1.4 mm from the round-4 reading). Console: the pilot eye is aft of the console and ~64 deg off its normal, so a point h above
# the art shows 1.2-1.7 h further forward (art +u), where the ON / OFF labels start 9.2 mm from the bezel centre: boss r 4.5 mm,
# 2.5 mm proud (image <= 8.7 mm), lever thrown toward ON (+v, up the panel; GEAR: down, toward DN), tip 4 mm above the art and
# 6.5 mm along the panel (image of the tip <= 8.6 mm forward, beside the ON label, not on it).
TG_BOSS = {'console': (0.0045, 0.0025), 'radio': (0.0060, 0.004)}
TG_TIP = {'console': (0.0040, 0.0065), 'radio': (0.0085, 0.003)}
# round 7: the COMM big knobs (now the FREQ selectors, label painted under them) 10 -> 7 mm proud: from the eye of their side the
# 10 mm knob's image clipped the top of the new FREQ label (check: 5-6 % of its text pixels); kind ('knob', r, h)
RADIO_CTRLS = [('COMM 1', ('knob', 0.0100, 0.007), 0.150, 0.532), ('COMM 2', ('knob', 0.0100, 0.007), 0.850, 0.532),
               ('VOL 1', ('knob', 0.0072), 0.150, 0.370), ('SQL 1', ('knob', 0.0072), 0.260, 0.370),
               ('VOL 2', ('knob', 0.0072), 0.740, 0.370), ('SQL 2', ('knob', 0.0072), 0.852, 0.370),
               ('IFF MODE', ('knob', 0.0110), 0.500, 0.196),
               ('PWR 1', 'dn', 0.1486, 0.1871), ('TEST 1', 'dn', 0.2606, 0.1871), ('PWR 2', 'dn', 0.7400, 0.1871), ('T/R+G 2', 'dn', 0.8526, 0.1871)]
# outboard panel columns: plate centres (world z). 1.9.14 r3 stacked them at 0.865 / 0.750 / 0.635: the LIGHTS plate
# (z 0.598-0.672) sat below the side-console top line seen from the crew eyes (100 % occluded). Round 4 stacks the three
# whole-panel crops down from z 0.922 (under the glare-shield lip line from the eyes) with 5 mm gaps: LIGHTS bottom 0.696.
COLUMN_TOP_Z, COLUMN_GAP = 0.922, 0.005


def art_cap(m, base, n, up, art, sub, mm_u, mm_v, height, sunk, striped=False):
    """raised cap over the painted control sub-rect `sub` (u0, v0, u1, v1) of panel art `art`: walls from `sunk` behind the art face
    to `height` in front, top = that crop of the art. Walls ck_black, or (striped) bands of the crop's own edge (a guard lid whose
    sides carry on the painted red / black stripes). mm_u / mm_v: metres per art u / v on this panel."""
    n, up = V(n).normalized(), V(up).normalized()
    side = up.cross(n).normalized()                     # = art right (n = right x up)
    u0, v0, u1, v1 = sub
    w, h = (u1 - u0) * mm_u, (v1 - v0) * mm_v
    d = height + sunk
    if not striped:
        obox_open(m, base + n * ((height - sunk) / 2), side, up, (w, h, d), 'ck_black')
    else:
        bu, bv = min(d / mm_u, (u1 - u0) / 3), min(d / mm_v, (v1 - v0) / 3)    # band of the crop as wide as the wall is tall
        P = lambda a, b, c_: base + side * (a * w / 2) + up * (b * h / 2) + n * (height if c_ > 0 else -sunk)
        for (q, uv, tw) in (
                ([P(-1, -1, 1), P(1, -1, 1), P(1, -1, -1), P(-1, -1, -1)], [(u0, v0), (u1, v0), (u1, v0 + bv), (u0, v0 + bv)], -up),
                ([P(-1, 1, 1), P(1, 1, 1), P(1, 1, -1), P(-1, 1, -1)], [(u0, v1), (u1, v1), (u1, v1 - bv), (u0, v1 - bv)], up),
                ([P(-1, -1, 1), P(-1, 1, 1), P(-1, 1, -1), P(-1, -1, -1)], [(u0, v0), (u0, v1), (u0 + bu, v1), (u0 + bu, v0)], -side),
                ([P(1, -1, 1), P(1, 1, 1), P(1, 1, -1), P(1, -1, -1)], [(u1, v0), (u1, v1), (u1 - bu, v1), (u1 - bu, v0)], side)):
            oriented_quad(m, q, 'ck_art', tw, [LY.uv(art, a, b) for a, b in uv])
    art_quad(m, base + n * height, side, up, w, h, art, u0, v0, u1, v1)


def guard_cover(m, base, n, up, art, sub, mm_u, mm_v):
    """guarded toggle: boss under a closed lid exactly the size of the painted striped cover, 3.5 mm proud, top = that crop of the
    art, sides = the crop's edge bands (striped). Round 5: the round-4 lid (16 mm proud on two black cheeks, open ends, 2.5 mm
    margin) showed a black cheek over half the guard from the near eye and the painted stripes again beside / under it.
    Closed and footprint = painted cover: the painted stripes are all under it; the painted guard frame round it stays seen."""
    n = V(n).normalized()
    cylinder(m, base - n * 0.002, base + n * 0.0015, 0.0055, N=10, mat='ck_black')     # boss (the control the checks find), 2 mm under the lid top
    art_cap(m, base, n, up, art, sub, mm_u, mm_v, 0.0035, 0.0005, striped=True)


def ctrl_toggle(m, base, n, d, tip, boss=None):
    """console / radio toggle on its painted bezel (round 5 / 6): low boss + short lever whose tip is `tip` = (height above the art
    face, offset along the lever direction d)."""
    n, d = V(n).normalized(), V(d).normalized()
    br, bh = boss or TG_BOSS['radio']
    cylinder(m, base - n * 0.002, base + n * bh, br, N=10, mat='ck_black')
    cylinder(m, base + n * (bh - 0.001), base + n * tip[0] + d * tip[1], 0.0022, 0.0018, N=6, mat='ck_struct')


def place_ctrl(m, kind, base, n, up, art=None, mm=None, u=None, v=None, tip='console'):
    """one modelled control at `base` (on the art face) of a panel facing n, art up = up, centred on painted (u, v) (see
    CONSOLE_CTRLS kinds)."""
    if kind == 'dn':
        ctrl_toggle(m, base, n, -V(up), TG_TIP[tip], TG_BOSS[tip])
    elif kind == 'up':
        ctrl_toggle(m, base, n, V(up), TG_TIP[tip], TG_BOSS[tip])
    elif kind[0] == 'guard':
        guard_cover(m, base, n, up, art, kind[1], *mm)
    elif kind[0] == 'knob':
        knob(m, base, n, r=kind[1], h=kind[2] if len(kind) > 2 else 0.012, top=kind[3] if len(kind) > 3 else 0.86,
             ptr=kind[4] if len(kind) > 4 else 0.002)
    elif kind[0] == 'cap':
        du, dv, hgt, sunk = kind[1:]
        art_cap(m, base, n, up, art, (u - du / 2, v - dv / 2, u + du / 2, v + dv / 2), *mm, hgt, sunk)
    else:
        raise ValueError(kind)


def basis(ux, uy):
    ux, uy = V(ux).normalized(), V(uy).normalized()
    n = ux.cross(uy).normalized()
    return Matrix((ux, uy, n)).transposed().to_quaternion()


def obox(m, c, ux, uy, size, mat):
    box(m, c, size, mat, rot=basis(ux, uy))


# ============================================================================================ panel-art helpers
def art_quad(m, c, ux, uy, w, h, name, u0=0.0, v0=0.0, u1=1.0, v1=1.0):
    """quad of w x h centred at c, facing ux x uy, mapped to the sub-rect (u0..u1, v0..v1) of art panel `name`."""
    ux, uy = V(ux).normalized(), V(uy).normalized()
    n = ux.cross(uy)
    q = [c - ux * w / 2 - uy * h / 2, c + ux * w / 2 - uy * h / 2, c + ux * w / 2 + uy * h / 2, c - ux * w / 2 + uy * h / 2]
    uv = [LY.uv(name, u0, v0), LY.uv(name, u1, v0), LY.uv(name, u1, v1), LY.uv(name, u0, v1)]
    oriented_quad(m, q, 'ck_art', n, uv)


def obox_open(m, c, ux, uy, size, mat):
    """box like obox but WITHOUT its front face (+ux x uy, the face the art quad covers) and its back face (against the mounting
    surface): 0.3.3, no hidden coplanar faces -> no z-fight."""
    ux, uy = V(ux).normalized(), V(uy).normalized()
    n = ux.cross(uy).normalized()
    w, h, d = (s_ / 2 for s_ in size)
    P = lambda a, b, cc: c + ux * (a * w) + uy * (b * h) + n * (cc * d)
    oriented_quad(m, [P(-1, -1, -1), P(1, -1, -1), P(1, -1, 1), P(-1, -1, 1)], mat, -uy)
    oriented_quad(m, [P(-1, 1, -1), P(1, 1, -1), P(1, 1, 1), P(-1, 1, 1)], mat, uy)
    oriented_quad(m, [P(-1, -1, -1), P(-1, 1, -1), P(-1, 1, 1), P(-1, -1, 1)], mat, -ux)
    oriented_quad(m, [P(1, -1, -1), P(1, 1, -1), P(1, 1, 1), P(1, -1, 1)], mat, ux)


def art_plate(m, c, ux, uy, w, h, name, depth=0.012, proud=0.004, mat='ck_panel', sub=(0.0, 0.0, 1.0, 1.0)):
    """panel plate with depth: body box `depth` deep (its front `proud` in front of c along the normal) + art face 0.5 mm in front.
    sub = (u0, v0, u1, v1): the part of the art panel to show (crops of a strip for small single sub-panels)."""
    ux, uy = V(ux).normalized(), V(uy).normalized()
    n = ux.cross(uy).normalized()
    obox_open(m, c + n * (proud - depth / 2), ux, uy, (w, h, depth), mat)
    art_quad(m, c + n * (proud + 0.0005), ux, uy, w - 0.002, h - 0.002, name, *sub)


def toggle(m, base, n, up, lever=0.022, guard=False):
    """small toggle switch standing on a panel: boss + bat lever tilted toward `up`; optional guard (two cheeks + lid)."""
    n, up = V(n).normalized(), V(up).normalized()
    cylinder(m, base - n * 0.002, base + n * 0.006, 0.0065, N=10, mat='ck_black')
    tip = base + n * (0.006 + lever * 0.92) + up * lever * 0.38
    cylinder(m, base + n * 0.005, tip, 0.0022, 0.0018, N=6, mat='ck_struct')
    if guard:
        side = up.cross(n).normalized()
        for s in (-1, 1):
            obox(m, base + side * (s * 0.011) + n * 0.012, up, n, (0.030, 0.024, 0.002), 'ck_black')
        obox(m, base + n * 0.025 - up * 0.002, side, up, (0.024, 0.030, 0.002), 'ck_black')


def knob(m, base, n, r=0.009, h=0.012, top=0.86, ptr=0.002):
    """knob: skirt r at the face tapering to top * r at h proud, centre pointer stub ptr high (defaults = every knob before
    round 6b; the left-console APU / NAV LT / FORM LT knobs are low, tapered discs, see CONSOLE_CTRLS)."""
    n = V(n).normalized()
    cylinder(m, base - n * 0.002, base + n * h, r, r * top, N=14, mat='ck_black')
    cylinder(m, base + n * h, base + n * (h + ptr), r * 0.3, N=6, mat='ck_struct')


def screen_in_bezel(m, c, ux, uy, w, h, face_mb, face_mat='screen', face_uv=None, art='mfd_bezel'):
    """display w x h set INTO a bezel: the bezel art (opening cut out, LY.BEZEL_OPEN) is a frame of 4 art quads around the
    opening on a bezel block 18 mm deep; the display face sits DISPLAY_RECESS behind the art face, LIP larger than the
    opening on every side; black backing behind. Returns the display face corners."""
    ux, uy = V(ux).normalized(), V(uy).normalized()
    n = ux.cross(uy).normalized()
    bu0, bv0, bu1, bv1 = LY.BEZEL_OPEN
    ow, oh = w - 2 * LIP, h - 2 * LIP                      # visible opening
    W, H = ow / (bu1 - bu0), oh / (bv1 - bv0)              # whole bezel so that the art opening matches the display opening
    front = c + n * 0.010                                  # bezel art face 10 mm proud of the panel face
    ox0 = -W / 2 + bu0 * W
    oy0 = -H / 2 + bv0 * H
    # bezel block (frame) behind the art: 4 boxes around the opening, 18 mm deep
    for (cx, cy, sw, sh) in (((ox0 + ow / 2), (oy0 + oh + (H / 2 - (oy0 + oh)) / 2), W, H / 2 - (oy0 + oh)),
                             ((ox0 + ow / 2), (-H / 2 + (oy0 + H / 2) / 2), W, oy0 + H / 2),
                             ((-W / 2 + (ox0 + W / 2) / 2), (oy0 + oh / 2), ox0 + W / 2, oh + 0.0004),
                             ((ox0 + ow + (W / 2 - (ox0 + ow)) / 2), (oy0 + oh / 2), W / 2 - (ox0 + ow), oh + 0.0004)):
        obox_open(m, front + ux * cx + uy * cy - n * 0.009, ux, uy, (sw, sh, 0.018), 'ck_black')
    # art frame (4 quads, UV = the same rect of the bezel art)
    def aq(x0, y0, x1, y1):
        a, b = (x0 + W / 2) / W, (y0 + H / 2) / H
        cc, d = (x1 + W / 2) / W, (y1 + H / 2) / H
        art_quad(m, front + n * 0.0005 + ux * ((x0 + x1) / 2) + uy * ((y0 + y1) / 2), ux, uy, x1 - x0, y1 - y0, art, a, b, cc, d)
    aq(-W / 2, oy0 + oh, W / 2, H / 2)
    aq(-W / 2, -H / 2, W / 2, oy0)
    aq(-W / 2, oy0, ox0, oy0 + oh)
    aq(ox0 + ow, oy0, W / 2, oy0 + oh)
    oc = front + ux * (ox0 + ow / 2) + uy * (oy0 + oh / 2)
    fc = oc - n * DISPLAY_RECESS
    corners = [fc - ux * (w / 2) - uy * (h / 2), fc + ux * (w / 2) - uy * (h / 2), fc + ux * (w / 2) + uy * (h / 2), fc - ux * (w / 2) + uy * (h / 2)]
    if face_mb is not None:
        oriented_quad(face_mb, corners, face_mat, n, face_uv or [(0, 0), (1, 0), (1, 1), (0, 1)])
    bk = fc - n * 0.002
    oriented_quad(m, [bk - ux * (ow / 2 + 0.003) - uy * (oh / 2 + 0.003), bk + ux * (ow / 2 + 0.003) - uy * (oh / 2 + 0.003),
                      bk + ux * (ow / 2 + 0.003) + uy * (oh / 2 + 0.003), bk - ux * (ow / 2 + 0.003) + uy * (oh / 2 + 0.003)], 'screen', n)
    return corners, (W, H)


# ============================================================================================ 1.8.4 ISIS movers (offline C)
# In game 1.8.2 the standby attitude showed no bank at 25 deg and the standby compass card was the same at headings 207 and 102: both were
# painted into atlas cells 0 / 2. 1.8.4: the attitude display gets a round horizon card (cell 3) and the nav display a heading card (cell 4)
# as movers (B-25H gauge frame: local +X toward the pilot, +angle about +X = clockwise seen by the pilot), the fixed aircraft symbol / lubber
# triangle sit 1 mm in front of the cards (cell 7, solid yellow), the engine page gets two torque pointers on its arcs (cell 6, white) and a
# fuel bar that scales along local +Y (cell 5, amber). Pixel positions = make_tiles_ga25x.py draw_* (256 px cells, y down from the top).
ISIS_CARD_R = 0.018
import b25h_v3_cockpit as _C3
PN, PU = _C3.PN, _C3.PU          # module-level copies for the 1.8.4 ISIS helpers (the builders bind them locally)


def _isis_pt(c, w, h, px, py, off):
    """display point of cell pixel (px, py) (cell_uv's 2 % margin), off metres in front of the face."""
    lu = (px / 256.0 - 0.5) * 2 / 0.96
    lv = (0.5 - py / 256.0) * 2 / 0.96
    return c + X_ * (lu * w / 2) + PU * (lv * h / 2) + PN * off


def _disc(mb, c, r, cell, N=32):
    for k in range(N):
        a0, a1 = 2 * math.pi * k / N, 2 * math.pi * (k + 1) / N
        pa = c + (X_ * math.sin(a0) + PU * math.cos(a0)) * r
        pb = c + (X_ * math.sin(a1) + PU * math.cos(a1)) * r
        uvs = [_C3.cell_uv(cell, 0, 0), _C3.cell_uv(cell, math.sin(a0), math.cos(a0)), _C3.cell_uv(cell, math.sin(a1), math.cos(a1))]
        tri = [mb.v(c), mb.v(pa), mb.v(pb)]
        if (pa - c).cross(pb - c).dot(PN) < 0:
            tri, uvs = [tri[0], tri[2], tri[1]], [uvs[0], uvs[2], uvs[1]]
        mb.face(tri, 'gauges', uvs, True)


def _quad(mb, pts, cell):
    oriented_quad(mb, pts, 'gauges', PN, [_C3.cell_uv(cell, -0.5, -0.5), _C3.cell_uv(cell, 0.5, -0.5), _C3.cell_uv(cell, 0.5, 0.5), _C3.cell_uv(cell, -0.5, 0.5)])


def isis_184(gf, isis):
    P = __import__('b25h_parts')
    from b25h_v3 import frame_x
    fr = frame_x(PN, PU)
    out = []
    # attitude: card centred on the symbol (cell px 128, 136), 1.5 mm in front of the face; symbol 2.5 mm
    c0, w, h = isis[0]
    ca = _isis_pt(c0, w, h, 128, 136, 0.0015)
    mb = MeshBuf(); _disc(mb, ca, ISIS_CARD_R, 3)
    out.append(P.Part('gauge_isis_att_card', 'cockpit_gauges', ca, mb, fr, info=dict(kind='gauge_card', value='bank (card roll) + pitch (card local +Y -0.0006 m/deg, +-20 deg)', driver='B25H.Instruments 1.8.4')))
    for x0, x1 in ((88, 114), (142, 168)):
        _quad(gf, [_isis_pt(c0, w, h, x0, 139, 0.0025), _isis_pt(c0, w, h, x1, 139, 0.0025), _isis_pt(c0, w, h, x1, 133, 0.0025), _isis_pt(c0, w, h, x0, 133, 0.0025)], 7)
    _quad(gf, [_isis_pt(c0, w, h, 124, 140, 0.0025), _isis_pt(c0, w, h, 132, 140, 0.0025), _isis_pt(c0, w, h, 132, 132, 0.0025), _isis_pt(c0, w, h, 124, 132, 0.0025)], 7)
    # nav: heading card on the rose centre (128, 112); lubber triangle in front
    c2, w, h = isis[2]
    cn = _isis_pt(c2, w, h, 128, 112, 0.0015)
    mb = MeshBuf(); _disc(mb, cn, ISIS_CARD_R, 4)
    out.append(P.Part('gauge_isis_hdg_card', 'cockpit_gauges', cn, mb, fr, info=dict(kind='gauge_card', value='card angle = -heading', driver='B25H.Instruments 1.8.4')))
    t = [_isis_pt(c2, w, h, 128, 76, 0.0025), _isis_pt(c2, w, h, 120, 116, 0.0025), _isis_pt(c2, w, h, 136, 116, 0.0025)]
    tri = [gf.v(p) for p in t]
    if (t[1] - t[0]).cross(t[2] - t[0]).dot(PN) < 0:
        tri = [tri[0], tri[2], tri[1]]
    gf.face(tri, 'gauges', [_C3.cell_uv(7, 0, 0.5), _C3.cell_uv(7, -0.5, -0.5), _C3.cell_uv(7, 0.5, -0.5)], True)
    # engine page: torque pointers at the arc centres (64 / 192, 92), 0 % at -120 deg, 100 % at +120 deg (plugin); rest 12 o'clock
    c1, w, h = isis[1]
    for k, L in enumerate('LR'):
        piv = _isis_pt(c1, w, h, 64 + k * 128, 92, 0.0015)
        tip = _isis_pt(c1, w, h, 64 + k * 128, 92 - 44, 0.0015)
        ln = (tip - piv).length
        mb = MeshBuf()
        _quad(mb, [piv - X_ * 0.0007 - PU * ln * 0.15, piv + X_ * 0.0007 - PU * ln * 0.15, tip + X_ * 0.0003, tip - X_ * 0.0003], 6)
        out.append(P.Part(f'gauge_isis_tq_{L}_needle', 'cockpit_gauges', piv, mb, fr, info=dict(kind='gauge_needle', value=f'torque % engine {L}: a0 -120, sweep 240 over 0..100 % (power / max power)', driver='B25H.Instruments 1.8.4')))
    # fuel bar (row 3 of the bars: x 71..235, y 224..236): pivot at its left end, local +Y = display right (the plugin scales Y)
    piv = _isis_pt(c1, w, h, 71, 230, 0.0012)
    mb = MeshBuf()
    _quad(mb, [_isis_pt(c1, w, h, 71, 236, 0.0012), _isis_pt(c1, w, h, 235, 236, 0.0012), _isis_pt(c1, w, h, 235, 225, 0.0012), _isis_pt(c1, w, h, 71, 225, 0.0012)], 5)
    from b25h_geom import frame_from_axes
    out.append(P.Part('gauge_isis_fuel_bar', 'cockpit_gauges', piv, mb, frame_x(PN, X_), info=dict(kind='gauge_bar', value='fuel fraction: local +Y scale', driver='B25H.Instruments 1.8.4')))
    for p in out:
        p.own_uv = True
    return out


def small_screen(m, c, ux, uy, w, h, face_mb, side=0.012, lift=0.0):
    """small display in a plain black bezel (aux panes): frame + recessed face + backing."""
    ux, uy = V(ux).normalized(), V(uy).normalized()
    n = ux.cross(uy).normalized()
    ow, oh = w - 2 * LIP, h - 2 * LIP
    c = c + n * lift
    cz = c + n * 0.005
    for s in (-1, 1):
        obox(m, cz + uy * (s * (oh / 2 + side / 2)), ux, uy, (ow + 2 * side, side, 0.016), 'ck_black')
        obox(m, cz + ux * (s * (ow / 2 + side / 2)), ux, uy, (side, oh + 0.0004, 0.016), 'ck_black')
    fc = c + n * (0.013 - DISPLAY_RECESS)
    corners = [fc - ux * (w / 2) - uy * (h / 2), fc + ux * (w / 2) - uy * (h / 2), fc + ux * (w / 2) + uy * (h / 2), fc - ux * (w / 2) + uy * (h / 2)]
    oriented_quad(face_mb, corners, 'screen', n, [(0, 0), (1, 0), (1, 1), (0, 1)])
    bk = fc - n * 0.002
    oriented_quad(m, [bk - ux * (ow / 2 + 0.003) - uy * (oh / 2 + 0.003), bk + ux * (ow / 2 + 0.003) - uy * (oh / 2 + 0.003),
                      bk + ux * (ow / 2 + 0.003) + uy * (oh / 2 + 0.003), bk - ux * (ow / 2 + 0.003) + uy * (oh / 2 + 0.003)], 'screen', n)
    return corners


# ============================================================================================ tub
def bulkhead_ring(y, inset):
    import b25h_v3 as V3
    from b25h_geom import RR_N
    fz = floor_z()
    pts = [V3.rr_point(y, j * 0.5, inset) for j in range(2 * RR_N)]
    out = []
    n = len(pts)
    for k in range(n):
        a, b = pts[k], pts[(k + 1) % n]
        if a.z >= fz:
            out.append(a)
        if (a.z - fz) * (b.z - fz) < 0:
            t = (fz - a.z) / (b.z - a.z)
            out.append(a.lerp(b, t))
    return out


def rear_bulkhead(m):
    y = BULKHEAD_Y
    front = bulkhead_ring(y + 0.018, 0.022)
    back = bulkhead_ring(y - 0.018, 0.022)
    fan_cap(m, front, sum(front, V()) / len(front), 'ck_struct', Y_)
    fan_cap(m, back, sum(back, V()) / len(back), 'ck_panel', -Y_)
    from b25h_geom import loft
    loft(m, [front, back], 'ck_panel', smooth=False)
    fz = floor_z()
    dw, dz0, dz1 = 0.46, fz + 0.04, 1.10
    for s in (-1, 1):
        box(m, (s * (dw / 2 + 0.015), y + 0.0195, (dz0 + dz1) / 2), (0.03, 0.006, dz1 - dz0), 'ck_panel')
    box(m, (0, y + 0.0195, dz1 + 0.015), (dw + 0.06, 0.006, 0.03), 'ck_panel')
    box(m, (0.17, y + 0.024, (dz0 + dz1) / 2), (0.025, 0.012, 0.16), 'ck_black')
    # placards on the bulkhead (behind the seats, seen when looking back)
    # placards at real size (0.3.2 fix pass: text cap height ~5-8 mm)
    # 1.9.14 round 4: art right = -x so the plate normal (ux x up) points FORWARD (+y, toward the crew); 1.9.13 / r3 used +x:
    # the art faced aft, 0.5 mm behind the bulkhead front face (y + 0.018) and back-face culled -> never seen
    for (x, z, w, h, name) in ((-0.40, 0.80, 0.075, 0.045, 'placard_danger'), (0.40, 0.80, 0.046, 0.029, 'placard_canopy'),
                               (0.40, 0.75, 0.060, 0.025, 'placard_nostep')):
        art_plate(m, V((x, y + 0.020, z)), -X_, UP, w, h, name, depth=0.004, proud=0.002)


def tub(m):
    """deck over the cannon feed (FLOOR_Z), footwells down at FOOT_Z (stock figures' heels), side walls, sill."""
    fz, fw = floor_z(), FOOT_Z
    T = 0.03
    y0 = BULKHEAD_Y + 0.02
    for s in (-1, 1):                                      # 0.3.3: deck = two side boxes + the centre strip (no coplanar end faces)
        box(m, (s * (CENTRE_FWD_HALF_X + WALL_X) / 2, (y0 + STEP_Y_OUT) / 2, fz - T / 2), (WALL_X - CENTRE_FWD_HALF_X, STEP_Y_OUT - y0, T), 'ck_struct')
    for s in (-1, 1):
        xc = s * (CENTRE_HALF_X + WELL_HALF_X) / 2
        box(m, (xc, (STEP_Y_OUT + WELL_CHAMFER[0]) / 2, WELL_PLATE_Z - 0.003), (WELL_HALF_X - CENTRE_HALF_X, WELL_CHAMFER[0] - STEP_Y_OUT, 0.006), 'ck_struct')
        box(m, (xc, STEP_Y_OUT + 0.0035, (WELL_PLATE_Z + fz - 0.003) / 2), (WELL_HALF_X - CENTRE_HALF_X, 0.006, fz - 0.003 - WELL_PLATE_Z), 'ck_struct')
        # chamfer plate over the nose-wheel well's chamfered top-front corner (the inner shins pass in front of it)
        a_, b_ = V((0, WELL_CHAMFER[0], WELL_PLATE_Z)), V((0, STEP_Y_IN, WELL_CHAMFER[1] + 0.002))
        d_ = b_ - a_
        nq = V((0, -d_.z, d_.y)).normalized()
        if nq.z < 0:
            nq = -nq
        box(m, V((xc, 0, 0)) + (a_ + b_) / 2 + nq * 0.001, (WELL_HALF_X - CENTRE_HALF_X, d_.length + 0.004, 0.006), 'ck_struct',
            rot=Quaternion(X_, math.atan2(d_.z, d_.y)))
    # centre cover strip: +-CENTRE_HALF_X over the breech, +-CENTRE_FWD_HALF_X ahead of it (recoil sleeve r 0.095): the stock
    # figures' toes (inner feet, |x| >= 0.106 at y 4.28) pass beside the narrow part
    box(m, (0, (y0 + FOOTWELL_Y) / 2, fz - T / 2), (2 * CENTRE_FWD_HALF_X, FOOTWELL_Y - y0, T), 'ck_struct')
    for s in (-1, 1):
        xo = s * (WELL_HALF_X + WALL_X) / 2
        box(m, (xo, (STEP_Y_OUT + FOOTWELL_Y) / 2, fw - T / 2), (WALL_X - WELL_HALF_X, FOOTWELL_Y - STEP_Y_OUT, T), 'ck_struct')
        xi = s * (CENTRE_HALF_X + WELL_HALF_X) / 2
        box(m, (xi, (STEP_Y_IN + 0.004 + FOOTWELL_Y) / 2, fw - T / 2), (WELL_HALF_X - CENTRE_HALF_X, FOOTWELL_Y - STEP_Y_IN - 0.004, T), 'ck_struct')
        h = fz - fw
        box(m, (xo, STEP_Y_OUT - 0.0135, fw + (h - 0.003) / 2), (WALL_X - WELL_HALF_X, 0.02, h - 0.003), 'ck_struct')   # top 3 mm under the deck top, front 3.5 mm behind the deck front (0.3.3 z-fight)
        hi = WELL_CHAMFER[1] + 0.004 - fw
        box(m, (xi, STEP_Y_IN + 0.0075, fw + hi / 2 - 0.0005), (WELL_HALF_X - CENTRE_HALF_X, 0.008, hi + 0.001), 'ck_struct')   # 3.5 mm off the well wall
        box(m, (s * (WELL_HALF_X + 0.01), (STEP_Y_OUT + STEP_Y_IN) / 2, fw + (h - 0.003) / 2), (0.02, STEP_Y_IN - STEP_Y_OUT, h - 0.003), 'ck_struct')
        box(m, (s * (CENTRE_FWD_HALF_X - 0.007), (STEP_Y_IN + 0.004 + FOOTWELL_Y) / 2, fw + (h - 0.003) / 2), (0.006, FOOTWELL_Y - STEP_Y_IN - 0.004, h - 0.003), 'ck_struct')   # 4 mm inside the strip edge
        # heel plates (anti-slip plates the heels rest on) and the riser ribs
        for side in (-1, 1):
            key = 'pilot' if s < 0 else 'wso'
            lp = leg_points(key, side)
            hx = lp['heel'].x
            if abs(hx) - 0.05 < CENTRE_HALF_X + 0.02:
                hx = s * (CENTRE_HALF_X + 0.075)
            box(m, (hx, lp['heel'].y + 0.06, fw + 0.0045), (0.10, 0.20, 0.006), 'ck_black')   # 1.5 mm proud of the floor (0.3.3)
    zt = PANEL_BOTTOM + 0.005
    box(m, (0, FOOTWELL_Y + 0.015, (fw + zt) / 2), (2 * WALL_X, 0.03, zt - fw), 'ck_struct')
    for s in (-1, 1):
        box(m, (s * (WALL_X + 0.009), (y0 + FOOTWELL_Y) / 2, (fw + SILL_Z) / 2), (0.018, FOOTWELL_Y - y0, SILL_Z - fw), 'ck_struct')
        box(m, (s * (WALL_X - 0.004), (2.75 + 4.42) / 2, SILL_Z + 0.012), (0.034, 4.42 - 2.75, 0.026), 'ck_panel')
        # wall stiffener ribs (frames) between seat and panel, as the stock tubs
        for yy in (3.00, 3.40):                                                        # (below the breaker panel)
            box(m, (s * (WALL_X - 0.012), yy, (fz + 0.62) / 2), (0.024, 0.04, 0.62 - fz), 'ck_panel')


def side_panels(m, key):
    """side console (sloped wall panel outboard of the legs, in front of the seat) + breaker panel on the wall beside the seat."""
    s = -1 if key == 'pilot' else 1
    art = 'console_left' if key == 'pilot' else 'console_right'
    # sloped console: from the wall (|x| = WALL_X, z 0.76) down-inboard to |x| 0.50, z 0.57; y 3.93 .. 4.33
    top = V((s * (WALL_X - 0.004), 0, 0.745))
    bot = V((s * 0.540, 0, 0.600))
    slope = (top - bot)
    uy = slope.normalized()                                # art up: up the slope (toward the wall)
    ux = Y_ if s < 0 else -Y_                              # art right: forward on the left wall, aft on the right wall
    nrm = ux.cross(uy)
    if nrm.x * s > 0:                                      # must face inboard
        ux = -ux
    yc, L = 4.062, 0.275                                   # y 3.925 .. 4.20 (seat front 3.909, panel face 4.23)
    c = (top + bot) / 2 + Y_ * yc
    art_plate(m, c, ux, uy, L, slope.length, art, depth=0.035, proud=0.004)
    # support web under the console down to the footwell floor-side wall (closed box: no floating shelf)
    n = ux.cross(uy).normalized()
    lowc = V((s * (0.540 + WALL_X) / 2 + s * 0.02, yc, 0.56))
    box(m, lowc, ((WALL_X - 0.540) - 0.04, L, 0.10), 'ck_panel')
    # relief: one modelled control on every painted one (CONSOLE_CTRLS, measured on the art). The art quad is the plate
    # less 1 mm a side (art_plate), so art (u, v) maps over L - 0.002 x slope - 0.002 (r3 used the plate size: <= 0.8 mm off)
    def at(u, v):
        return c + ux * ((u - 0.5) * (L - 0.002)) + uy * ((v - 0.5) * (slope.length - 0.002)) + n * 0.0045
    for name, kind, u, v in CONSOLE_CTRLS[art]:
        place_ctrl(m, kind, at(u, v), n, uy, art=art, mm=(L - 0.002, slope.length - 0.002), u=u, v=v)
    # circuit-breaker panel on the wall beside the seat (vertical, facing inboard), above the seat side, under the sill
    bx = s * (WALL_X - 0.002)
    bux = Y_ if s < 0 else -Y_
    if bux.cross(UP).x * s > 0:
        bux = -bux
    # 0.3.2 fix pass: real-size wall panels (breaker heads ~13 mm: the breaker art's heads are 3.9 % of its width -> 0.34 m wide),
    # two breaker panels + a lights / standby strip under them, small placards (cap height ~6 mm)
    BW_, BH_ = 0.34, 0.34 / LY.aspect('breakers')
    for yy in (3.17, 3.55):
        art_plate(m, V((bx, yy, 0.800)), bux, UP, BW_, BH_, 'breakers', depth=0.012, proud=0.004)
    art_plate(m, V((bx, 3.36, 0.700)), bux, UP, 0.30, 0.30 / LY.aspect('subpanel'), 'subpanel', depth=0.012, proud=0.004)
    # round 6: the sub-strip art no longer carries the LDG / TAXI / STBY toggle levers (painted out; the lever is the model), so
    # this wall copy of the strip gets the same modelled toggles on the painted nuts (it had painted levers only)
    wn, ww, wh = bux.cross(UP).normalized(), 0.30 - 0.002, 0.30 / LY.aspect('subpanel') - 0.002
    for (u, v) in SUB_TOGGLES:
        toggle(m, V((bx, 3.36, 0.700)) + bux * ((u - 0.5) * ww) + UP * ((v - 0.5) * wh) + wn * 0.0045, wn, -UP, lever=0.012)
    if s < 0:
        art_plate(m, V((bx, 3.80, 0.805)), bux, UP, 0.031, 0.020, 'placard_glimit', depth=0.004, proud=0.002)
    else:
        art_plate(m, V((bx, 3.80, 0.805)), bux, UP, 0.057, 0.035, 'placard_fuel', depth=0.004, proud=0.002)
    art_plate(m, V((bx, 3.80, 0.760)), bux, UP, 0.046, 0.029, 'placard_canopy', depth=0.004, proud=0.002)


def centre_pedestal(m, thr, arm):
    """throttle quadrant: arc housing concentric with the stock throttle pivot (axis X through thr); radius R_ARC under the stock
    grip's lowest radius (0.169 m from the pivot: 4 mm gap) over the lever's whole travel; slot down the middle; body down to
    the centre cover strip; sloped front with the radio panel up into the instrument panel. `arm` (child of the lever) gets
    the stalk that comes up out of the slot into the grip."""
    fz = floor_z()
    R_ARC = 0.1737                                         # stock sfb_throttle min radius from its pivot 0.1777 m - 4 mm
    hx = 0.112
    a0, a1 = math.radians(-62), math.radians(28)           # angle from straight up, + = forward (grip: 36.6..50.5 aft at 0 deg, 52 deg travel)
    N = 18
    def P(a, r=R_ARC):
        return V((0, thr.y + r * math.sin(a), thr.z + r * math.cos(a)))
    ring = [P(a0 + (a1 - a0) * k / N) for k in range(N + 1)]
    # 0.3.3: a REAL slot opening for the split lever: from SLOT_A0 to SLOT_A1 the arc top is two strips (x beyond +-SLOT_HX),
    # with slot walls 30 mm deep and a dark slot floor; outside that range the arc is closed. Art u is cropped to match.
    sa0, sa1 = math.radians(SLOT_A0), math.radians(SLOT_A1)
    knots = [math.radians(k[0]) for k in LY.QG_V_KNOTS]
    angs = sorted(set([a0 + (a1 - a0) * k / N for k in range(N + 1)] + [sa0, sa1] + [k for k in knots if a0 <= k <= a1]))
    origin = V((0, thr.y, thr.z))

    def art_v(ang):
        # 0.3.4: piecewise-linear through the measured landmarks of the fal quadrant art (ga25x_ckart_layout.QG_V_KNOTS):
        # the painted slot ends sit on the geometry slot ends, the IDLE tick at the lever's 0 deg angle, MAX at 52 deg
        dg = math.degrees(ang)
        kn = LY.QG_V_KNOTS
        for (d0, v0), (d1, v1) in zip(kn, kn[1:]):
            if dg <= d1 + 1e-9:
                return v0 + (v1 - v0) * (dg - d0) / (d1 - d0)
        return kn[-1][1]
    uL, uR = LY.QG_SLOT_U                                  # painted slot edges -> geometry slot edges (x = -+SLOT_HX)
    for k in range(len(angs) - 1):
        aa, bb = angs[k], angs[k + 1]
        a, b = P(aa), P(bb)
        va, vb = art_v(aa), art_v(bb)
        nrm = ((a + b) / 2 - origin).normalized()
        in_slot = sa0 - 1e-6 <= (aa + bb) / 2 <= sa1 + 1e-6
        spans = [(-hx, -SLOT_HX, 0.0, uL), (SLOT_HX, hx, uR, 1.0)] + ([] if in_slot else [(-SLOT_HX, SLOT_HX, uL, uR)])
        for x0, x1, u0, u1 in spans:
            q = [V((x0, a.y, a.z)), V((x1, a.y, a.z)), V((x1, b.y, b.z)), V((x0, b.y, b.z))]
            uv = [LY.uv('pedestal_gate', u0, va), LY.uv('pedestal_gate', u1, va), LY.uv('pedestal_gate', u1, vb), LY.uv('pedestal_gate', u0, vb)]
            oriented_quad(m, q, 'ck_art', nrm, uv)
        if in_slot:
            ai, bi = P(aa, R_ARC - SLOT_DEPTH), P(bb, R_ARC - SLOT_DEPTH)
            for sx in (-1, 1):                             # slot side walls, facing into the slot
                oriented_quad(m, [V((sx * SLOT_HX, a.y, a.z)), V((sx * SLOT_HX, b.y, b.z)), V((sx * SLOT_HX, bi.y, bi.z)), V((sx * SLOT_HX, ai.y, ai.z))],
                              'ck_black', V((-sx, 0, 0)))
            oriented_quad(m, [V((-SLOT_HX, ai.y, ai.z)), V((SLOT_HX, ai.y, ai.z)), V((SLOT_HX, bi.y, bi.z)), V((-SLOT_HX, bi.y, bi.z))], 'ck_black', nrm)
    for ang, sgn in ((sa0, 1), (sa1, -1)):                 # slot end walls
        o_, i_ = P(ang), P(ang, R_ARC - SLOT_DEPTH)
        tang = V((0, math.cos(ang), -math.sin(ang)))
        oriented_quad(m, [V((-SLOT_HX, o_.y, o_.z)), V((SLOT_HX, o_.y, o_.z)), V((SLOT_HX, i_.y, i_.z)), V((-SLOT_HX, i_.y, i_.z))], 'ck_black', tang * sgn)
    # side walls: from the arc down to the deck (closed fan)
    for sx in (-1, 1):                                     # quads per arc segment (no n-gons)
        for k in range(N):
            a, b = ring[k], ring[k + 1]
            oriented_quad(m, [V((sx * hx, a.y, fz)), V((sx * hx, a.y, a.z)), V((sx * hx, b.y, b.z)), V((sx * hx, b.y, fz))], 'ck_panel', V((sx, 0, 0)))
    # aft end wall (vertical), under the arc's aft edge
    oriented_quad(m, [V((-hx, ring[0].y, fz)), V((hx, ring[0].y, fz)), V((hx, ring[0].y, ring[0].z)), V((-hx, ring[0].y, ring[0].z))], 'ck_panel', -Y_)
    # trim rails along both arc edges (6 mm proud, catch the light like the stock quadrant)
    for sx in (-1, 1):
        for k in range(N):
            a, b = ring[k], ring[k + 1]
            cylinder(m, V((sx * (hx - 0.009), a.y, a.z)), V((sx * (hx - 0.009), b.y, b.z)), 0.005, N=6, mat='ck_black', cap0=(k == 0), cap1=(k == N - 1))
    # front: flat deck from the arc's front edge forward to RADIO_Y, then the radio / IFF panel standing vertical up to the
    # instrument panel underside (the stock grip at full throttle reaches y thr+0.091, z thr+0.341: clear of both)
    RADIO_Y = 4.275
    f0 = ring[-1]
    oriented_quad(m, [V((-hx, f0.y, f0.z)), V((hx, f0.y, f0.z)), V((hx, RADIO_Y, f0.z)), V((-hx, RADIO_Y, f0.z))], 'ck_panel', UP)
    zt = PANEL_BOTTOM + 0.004
    rh = zt - f0.z
    rc = V((0, RADIO_Y - 0.0005, (f0.z + zt) / 2))
    art_quad(m, rc, X_, UP, 2 * hx, rh, 'pedestal_radio')
    oriented_quad(m, [V((-hx, RADIO_Y, fz)), V((hx, RADIO_Y, fz)), V((hx, RADIO_Y, f0.z)), V((-hx, RADIO_Y, f0.z))], 'ck_panel', -Y_)
    for sx in (-1, 1):
        oriented_quad(m, [V((sx * hx, f0.y, fz)), V((sx * hx, f0.y, f0.z)), V((sx * hx, RADIO_Y, f0.z)), V((sx * hx, RADIO_Y, fz))], 'ck_panel', V((sx, 0, 0)))
        oriented_quad(m, [V((sx * hx, RADIO_Y, f0.z)), V((sx * hx, RADIO_Y, zt)), V((sx * hx, 4.33, zt)), V((sx * hx, 4.33, f0.z))], 'ck_panel', V((sx, 0, 0)))
    # 1.9.14 round 4: one modelled control on every painted one (RADIO_CTRLS, measured); r3 had four knobs on the blank top
    # border by COMM 1 / COMM 2 (~30 mm above the painted VOL / SQL knobs)
    for name, kind, u, v in RADIO_CTRLS:
        base = rc + X_ * ((u - 0.5) * 2 * hx) + UP * ((v - 0.5) * rh) - Y_ * 0.0005
        if kind[0] == 'knob':
            knob(m, base, -Y_, r=kind[1], h=kind[2] if len(kind) > 2 else 0.010)
        else:
            place_ctrl(m, kind, base, -Y_, UP, tip='radio')
    # friction knob on the quadrant side
    cylinder(m, V((hx, thr.y + 0.02, thr.z + 0.10)), V((hx + 0.018, thr.y + 0.02, thr.z + 0.10)), 0.013, N=14, mat='ck_black')
    # 0.3.4 SPLIT THROTTLE HANDLE = fal-generated model (user: all art assets through fal / the Universal Modder pipeline):
    # concept (google/nano-banana-2.1) -> image-to-3D (tripo3d/h3.1) -> remesh (tripo3d/tripo/remesh, ~6k faces) ->
    # assets/model_ga25x/src/throttle_gen/throttle_tripo_remesh.glb; fitted here (throttle_handle) onto the lever pivot.
    throttle_handle(arm, thr, R_ARC - SLOT_DEPTH + 0.002)
    return R_ARC


THROTTLE_GLB = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'assets', 'model_ga25x', 'src', 'throttle_gen',
                            'throttle_tripo_remesh.glb')
GLB_CUT = 0.22          # lower 22 % of the generated model (pivot clevis + cross pin, wider than the slot) is cut: it would sit
                        # inside the housing under the slot floor, never seen
GLB_STEM_FIT = 0.021    # half width of the two stems (model y) after scaling: 4 mm inside the slot half width 0.025


def read_glb(path):
    """minimal GLB reader (no bpy import: the glTF importer left dangling view-layer entries in the build scene). Returns
    (all points, [(triangle points, triangle uvs)]) in Blender axes (glTF Y-up -> Z-up: (x, y, z) -> (x, -z, y); v -> 1 - v),
    node transforms identity (tripo export: one node, no transform)."""
    import json, struct
    d = open(os.path.abspath(path), 'rb').read()
    L = struct.unpack('<III', d[:12])[2]
    off, chunks = 12, []
    while off < L:
        cl, ct = struct.unpack('<II', d[off:off + 8]); chunks.append(d[off + 8:off + 8 + cl]); off += 8 + cl
    js, bn = json.loads(chunks[0]), chunks[1]
    assert all('matrix' not in n and 'rotation' not in n and 'scale' not in n and 'translation' not in n for n in js['nodes'])
    def acc(i):
        a = js['accessors'][i]; bv = js['bufferViews'][a['bufferView']]
        o = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
        nc = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3}[a['type']]
        fmt = {5126: 'f', 5123: 'H', 5125: 'I'}[a['componentType']]
        sz = struct.calcsize(fmt)
        stride = bv.get('byteStride', sz * nc)
        return [struct.unpack_from('<' + fmt * nc, bn, o + k * stride) for k in range(a['count'])]
    pts_all, tris = [], []
    for mesh in js['meshes']:
        for pr in mesh['primitives']:
            P_ = [V((x, -z, y)) for x, y, z in acc(pr['attributes']['POSITION'])]
            T_ = [(u, 1.0 - v) for u, v in acc(pr['attributes']['TEXCOORD_0'])]
            I_ = [i[0] for i in acc(pr['indices'])]
            pts_all += P_
            for k in range(0, len(I_), 3):
                a_, b_, c_ = I_[k], I_[k + 1], I_[k + 2]
                tris.append(([P_[a_], P_[b_], P_[c_]], [T_[a_], T_[b_], T_[c_]]))
    return pts_all, tris


def throttle_handle(arm, thr, r_floor):
    """import the fal-generated split throttle (GLB, Blender Z-up after import: z = lever length, y = the two halves side by
    side, x = depth), cut the hidden pivot end, scale it uniformly so the two stems fit the slot (GLB_STEM_FIT), and lay it
    along the lever direction at 0 deg (LEVER_DEG): model z -> radial out of the slot, model y -> aircraft x (left / right
    halves), model x -> forward along the travel. Faces carry the model's own UVs (material ck_throttle: its baked base colour
    + normal map, ga25x_throttle_b/_n). Appends to `arm` (world coordinates; the part pivot is the lever pivot)."""
    pts, polys = read_glb(THROTTLE_GLB)
    zmin, zmax = min(v.z for v in pts), max(v.z for v in pts)
    zc = zmin + GLB_CUT * (zmax - zmin)
    stem = [v for v in pts if zc <= v.z <= zmin + 0.5 * (zmax - zmin)]
    yc = (max(v.y for v in stem) + min(v.y for v in stem)) / 2
    xc = (max(v.x for v in stem) + min(v.x for v in stem)) / 2
    sc = GLB_STEM_FIT / ((max(v.y for v in stem) - min(v.y for v in stem)) / 2)
    ga = math.radians(LEVER_DEG)
    d = V((0, math.sin(ga), math.cos(ga)))
    t = V((0, math.cos(ga), -math.sin(ga)))
    base = V((0, thr.y, thr.z)) + d * r_floor
    def W(v):
        return base + d * ((v.z - zc) * sc) + X_ * ((v.y - yc) * sc) - t * ((v.x - xc) * sc)   # -t: keeps the model right-handed (no winding flip)
    n_in, out = 0, []
    for vs, uvs in polys:
        if max(v.z for v in vs) <= zc:
            continue                                       # hidden pivot end (under the slot floor)
        if min(v.z for v in vs) < zc:                      # clip at the cut plane (stems keep their full length), UVs interpolated
            ov, ou = [], []
            for k in range(len(vs)):
                p0, p1, u0, u1 = vs[k], vs[(k + 1) % len(vs)], uvs[k], uvs[(k + 1) % len(vs)]
                if p0.z >= zc:
                    ov.append(p0); ou.append(u0)
                if (p0.z - zc) * (p1.z - zc) < 0:
                    f = (zc - p0.z) / (p1.z - p0.z)
                    ov.append(p0.lerp(p1, f)); ou.append((u0[0] + (u1[0] - u0[0]) * f, u0[1] + (u1[1] - u0[1]) * f))
            cv_, cu_ = [], []
            for pv_, pu_ in zip(ov, ou):                   # drop near-duplicate points of the clip
                if not cv_ or (pv_ - cv_[-1]).length > 1e-6:
                    cv_.append(pv_); cu_.append(pu_)
            if len(cv_) > 1 and (cv_[0] - cv_[-1]).length <= 1e-6:
                cv_.pop(); cu_.pop()
            if len(cv_) < 3:
                continue
            for k in range(1, len(cv_) - 1):              # fan into triangles (clean, planar pieces)
                out.append(([W(cv_[0]), W(cv_[k]), W(cv_[k + 1])], [cu_[0], cu_[k], cu_[k + 1]]))
            continue
        out.append(([W(v) for v in vs], uvs))
    # the generated mesh has a few doubled shells on the stems (two same-facing surfaces < 1 mm apart = z-fight): drop the smaller
    # face of every such pair (BVH: centroid within 1 mm of another same-facing face, along its normal)
    from mathutils.bvhtree import BVHTree
    vv, ff = [], []
    for ws, _ in out:
        ff.append(tuple(range(len(vv), len(vv) + len(ws)))); vv += ws
    bvh = BVHTree.FromPolygons(vv, ff)
    def nrm_area(ws):
        n_ = V((0, 0, 0))
        for k in range(1, len(ws) - 1):
            n_ += (ws[k] - ws[0]).cross(ws[k + 1] - ws[0])
        return (n_.normalized() if n_.length > 0 else n_), n_.length / 2
    na = [nrm_area(ws) for ws, _ in out]
    drop = set()
    for i, (ws, _) in enumerate(out):
        if i in drop:
            continue
        c = sum(ws, V()) / len(ws)
        hits = {}
        sps = [c] + [w.lerp(c, 0.5) for w in ws]
        for k in range(1, len(ws) - 1):                    # + the same 4 x 4 barycentric grid the z-fight check samples
            for a_ in (0.125, 0.375, 0.625, 0.875):
                for b_ in (0.125, 0.375, 0.625, 0.875):
                    if a_ + b_ < 1:
                        sps.append(ws[0] + (ws[k] - ws[0]) * a_ + (ws[k + 1] - ws[0]) * b_)
        for sp in sps:
            for (co, _n, j, dd) in bvh.find_nearest_range(sp, 0.001):
                if j is None or j == i or j in drop:
                    continue
                off_ = sp - co
                if na[i][0].dot(na[j][0]) > 0.999 and (off_ - na[j][0] * off_.dot(na[j][0])).length < 0.0002:
                    hits[j] = hits.get(j, 0) + 1
        for j, k in hits.items():
            if k >= 1 and i not in drop:
                drop.add(i if na[i][1] <= na[j][1] else j)
    for i, (ws, uvs) in enumerate(out):
        if i not in drop:
            arm.poly(ws, 'ck_throttle', uvs, smooth=True)
            n_in += 1
    print(f'[cockpit] throttle handle: dropped {len(drop)} doubled-shell faces')
    print(f'[cockpit] throttle handle from {os.path.basename(THROTTLE_GLB)}: {n_in} of {len(polys)} faces, scale {sc:.4f}, '
          f'length {(zmax - zc) * sc * 1000:.0f} mm, stems +-{GLB_STEM_FIT * 1000:.0f} mm')


def stick_mount(m, sp):
    """mount boot under a stock stick base: from the footwell floor up to the stick base (the stock stick starts 5 mm above its pivot)."""
    fw = FOOT_Z
    top = sp.z + 0.004
    cylinder(m, V((sp.x, sp.y, fw - 0.002)), V((sp.x, sp.y, top - 0.03)), 0.060, 0.042, N=18, mat='ck_black')     # rubber boot
    cylinder(m, V((sp.x, sp.y, top - 0.031)), V((sp.x, sp.y, top)), 0.036, 0.028, N=18, mat='ck_struct')         # collar the stick sits in
    box(m, (sp.x, sp.y, fw + 0.004), (0.15, 0.15, 0.008), 'ck_panel')                                          # floor plate


def pedals(key, L):
    """rudder pedals of one crew: one plate under the ball of each foot, plane tilted PEDAL_TILT from the floor (face normal
    aft and up: the foot presses forward/down), on arms down to a yaw bar that stands on the footwell floor (centre post).
    Object origin = yaw pivot on the floor, local +X (Unity) = up (ControlSurface.yawRange)."""
    P = __import__('b25h_parts')
    sx = S.CREW[key]['seat'][0]
    pm = MeshBuf()
    PEDAL_TILT = math.radians(24)
    fw = FOOT_Z
    bar_y, bar_z = 4.31, fw + 0.055
    pivot = V((sx, bar_y, fw))
    cylinder(pm, V((sx, bar_y, fw - 0.002)), V((sx, bar_y, bar_z)), 0.028, N=14, mat='ck_black')          # post on the floor
    cylinder(pm, V((sx - 0.22, bar_y, bar_z)), V((sx + 0.22, bar_y, bar_z)), 0.014, N=10, mat='ck_black')  # yaw bar
    plates = []
    for side in (-1, 1):
        lp = leg_points(key, side)
        heel, st = lp['heel'], lp['sole_toe']
        sole = (st - heel)
        ball = heel + sole * 0.72                                  # ball of the foot on the sole line
        x = ball.x
        ax = V((0, math.cos(PEDAL_TILT), math.sin(PEDAL_TILT)))    # plate long axis (forward-up)
        nrm = V((0, -math.sin(PEDAL_TILT), math.cos(PEDAL_TILT)))  # plate face normal: aft and up
        sole_slope = sole.z / max(1e-6, sole.y)
        # plate top touches the sole line 5 mm ahead of its front edge -> 1 cm under the sole at the ball
        c = V((x, ball.y, ball.z)) - nrm * 0.010 - nrm * 0.004
        plate_l, plate_w, plate_t = 0.120, 0.080, 0.014
        box(pm, c - nrm * (plate_t / 2), (plate_w, plate_l, plate_t), 'ck_panel', rot=basis(X_, ax) if False else Quaternion(X_, PEDAL_TILT))
        # tread strips on the face
        for k in range(4):
            box(pm, c + ax * (-0.045 + 0.03 * k) + nrm * 0.0015, (plate_w - 0.016, 0.008, 0.003), 'ck_black', rot=Quaternion(X_, PEDAL_TILT))
        # arm: from the plate's lower front down to the yaw bar
        fr = c + ax * (plate_l / 2 - 0.01) - nrm * plate_t
        cylinder(pm, fr, V((x, bar_y, bar_z)), 0.011, N=8, mat='ck_black')
        plates.append(dict(centre=c, normal=nrm, axis=ax, side=side, ball=ball, heel=heel, knee=lp['knee'], sole_slope=sole_slope))
    part = P.Part(f'cockpit_rudder_pedals_{L}', 'fus_cockpit', pivot, pm, frame_from_axes(V((0, 0, 1)), V((0, 1, 0))),
                  info=dict(kind='rudder_pedals', axis_local='+X (Unity) = up', range_deg=15, drive='ControlSurface.yawRange',
                            plates=[dict(centre=tuple(round(v, 4) for v in p['centre']), normal=tuple(round(v, 4) for v in p['normal']),
                                         knee=tuple(round(v, 4) for v in p['knee']), heel=tuple(round(v, 4) for v in p['heel']))
                                    for p in plates],
                            note='0.3.2: plates under the ball of each foot of the stock figure (COIN bone pose), tilted 24 deg, '
                                 'face normal aft-up; yaw bar on a post standing on the footwell floor'))
    return part


# ============================================================================================ cockpit
def build_cockpit():
    import b25h_v3_cockpit as C3
    P = __import__('b25h_parts')
    m = MeshBuf()
    gf = MeshBuf()
    parts = []
    PN, PU = C3.PN, C3.PU

    tub(m)
    rear_bulkhead(m)

    # ---------------------------------------------------------------- stock controls (empties; meshes added in Unity)
    root = figure_root('pilot')
    thr = V((0.0, root.y + THROTTLE_FROM_ROOT[0] + THROTTLE_EXTRA_FWD, root.z + THROTTLE_FROM_ROOT[1] - THROTTLE_DROP))
    arm = MeshBuf()
    centre_pedestal(m, thr, arm)
    parts.append(P.Part('cockpit_throttle', 'fus_cockpit', thr, None, Quaternion(),
                        info=dict(kind='throttle', drive='Cockpit.throttles rotation', range_deg=THROTTLE_RANGE,
                                  note='EMPTY = the lever pivot (Unity identity frame); 0.3.3: NO stock mesh (user: the stock levers were not attached), '
                                       'our split lever is the child cockpit_throttle_arm. '
                                       f'SFB-81 spot relative to the pilot figure + {THROTTLE_EXTRA_FWD} m forward (clears the stock seat). '
                                       '0.3.2: the quadrant housing is an arc concentric with this pivot (grip 4 mm above it); child '
                                       'cockpit_throttle_arm = our stalk out of the slot')))
    parts.append(P.Part('cockpit_throttle_arm', 'cockpit_throttle', thr, arm,
                        info=dict(kind='throttle_lever', slot_half_x=SLOT_HX, slot_deg=(SLOT_A0, SLOT_A1), r_arc=0.1737, slot_depth=SLOT_DEPTH,
                                  note='0.3.3 split throttle lever (two halves + grip heads + gang bar) out of the quadrant slot; '
                                       'rotates with cockpit_throttle (Cockpit.throttles 0..52 deg: IDLE -> MAX)')))
    for side, L, key in ((-1, 'L', 'pilot'), (1, 'R', 'wso')):
        r = figure_root(key)
        sp = V((r.x + side * STICK_FROM_ROOT[0], r.y + STICK_FROM_ROOT[1], r.z + STICK_FROM_ROOT[2]))
        stick_mount(m, sp)
        parts.append(P.Part(f'stick_{L}', 'fus_cockpit', sp, None, Quaternion(),
                            info=dict(kind='stock_stick', stock_mesh='sfb_joystick', stock_materials=['hotas', 'SFB_cockpit'],
                                      drive='Cockpit.joysticks (localEulerAngles = (pitch*range, 0, -roll*range))', range_deg=STICK_RANGE,
                                      note='EMPTY: GA25XBuild adds the stock SFB-81 joystick; placed as SFB-81 joystick_' + L +
                                           ' relative to its crew figure; 0.3.2: stands on a mount boot on the deepened footwell floor')))
        if key == 'wso':
            parts.append(P.Part('crew_wso_eye', 'fus_cockpit', S.CREW[key]['eye'], None,
                                info=dict(kind='crew_eye', crew='wso', look='+Z (Unity) forward')))
        parts.append(pedals(key, L))
        side_panels(m, key)

    # ---------------------------------------------------------------- instrument panel (with depth) + glareshield
    PC = C3.panel_pt(0, (PANEL_BOTTOM + PANEL_TOP) / 2)
    ph = (PANEL_TOP - PANEL_BOTTOM) / math.cos(math.radians(S.PANEL_RAKE))
    obox(m, PC - PN * 0.051, X_, PU, (1.36, ph, 0.090), 'ck_panel')                    # panel body 9 cm deep (front 6 mm behind the art face plate)
    # side cheeks (panel ends) and a hood over the top so the panel reads as a recessed console
    for s in (-1, 1):
        box(m, (s * 0.672, 4.30, (PANEL_BOTTOM + GZ) / 2), (0.03, 0.22, GZ - PANEL_BOTTOM), 'ck_panel')
    box(m, (0, (LIP_Y + 4.50) / 2, GZ), (1.32, 4.50 - LIP_Y, 0.020), 'ck_black')                    # glareshield top
    cylinder(m, V((-0.655, LIP_Y, GZ - 0.004)), V((0.655, LIP_Y, GZ - 0.004)), 0.016, N=14, mat='ck_black')   # padded lip
    # blank art plates fill the panel face around the instruments (riveted panel texture, not a flat slab)
    art_plate(m, C3.panel_pt(0.0, (PANEL_BOTTOM + PANEL_TOP) / 2), X_, PU, 1.34, ph - 0.004, 'blank', depth=0.006, proud=0.001)

    MFDS = [('mfd_center', -MAIN_X, MAIN_Z, MAIN_W, MAIN_H, 'pilot main display (tac screen = Cockpit.tacScreenRender)'),
            ('mfd_right', MAIN_X, MAIN_Z, MAIN_W, MAIN_H, 'weapons officer main display (target camera)')]
    bez = {}
    for nmn, x, z, w, h, note in MFDS:
        sm = MeshBuf()
        cs, (BW, BH) = screen_in_bezel(m, C3.panel_pt(x, z), X_, PU, w, h, sm)
        bez[nmn] = (BW, BH)
        c = sum(cs, V()) / 4
        mp = P.Part(nmn, 'fus_cockpit', c, sm, info=dict(kind='mfd', size_m=(w, h), normal_unity=(0.0, round(PN.z, 4), round(PN.y, 4)),
                                                        uv='0-1; u -> crew right, v -> panel up', note=note,
                                                        bezel=f'bezel art {BW:.3f} x {BH:.3f} m with 20 push buttons; lip {LIP * 1000:.0f} mm, face {DISPLAY_RECESS * 1000:.0f} mm behind the bezel face'))
        mp.own_uv = True
        parts.append(mp)
    for nmn, x in (('mfd_left', -AUX_X), ('mfd_wso', AUX_X)):
        sm = MeshBuf()
        cs = small_screen(m, C3.panel_pt(x, AUX_Z), X_, PU, AUX_W, AUX_H, sm)
        c = sum(cs, V()) / 4
        mp = P.Part(nmn, 'fus_cockpit', c, sm, info=dict(kind='mfd', size_m=(AUX_W, AUX_H), normal_unity=(0.0, round(PN.z, 4), round(PN.y, 4)),
                                                        uv='0-1; u -> crew right, v -> panel up',
                                                        note=('pilot' if x < 0 else 'weapons officer') + ' auxiliary pane (generator: Touchscreen_off or tac screen)'))
        mp.own_uv = True
        parts.append(mp)
    # annunciator rows under the glareshield lip, one per crew (12 caution lights each), on a small sloped strip
    ann_h = 0.046
    for x in (-MAIN_X, MAIN_X):
        art_plate(m, C3.panel_pt(x, PANEL_TOP - 0.052), X_, PU, ann_h * LY.aspect('annunciator') * 0.98, ann_h, 'annunciator', depth=0.016, proud=0.012)
    # sub-panel switch strips under the main displays (HUD / MFD BRT / ALT / LIGHTS / STBY / CLOCK / MASTER MODE)
    sp_h = 0.076
    for x in (-0.205, 0.205):
        art_plate(m, C3.panel_pt(x, 0.500), X_, PU, sp_h * LY.aspect('subpanel'), sp_h, 'subpanel', depth=0.016, proud=0.010)
        n = PN
        cz = C3.panel_pt(x, 0.500) + n * 0.0105
        w_ = sp_h * LY.aspect('subpanel')
        # 1.9.14: knobs / toggles on the painted ones of subpanel_strip.png (measured; u right, v up, radius in strip heights)
        for i_, (u, v, rr) in enumerate(SUB_KNOBS):
            lo_ = SUB_KNOB_LOW.get(i_)
            knob(m, cz + X_ * ((u - 0.5) * w_) + PU * ((v - 0.5) * sp_h), n, r=rr * sp_h, h=lo_[0] if lo_ else 0.009,
                 top=lo_[2] if lo_ else 0.86, ptr=lo_[3] if lo_ else 0.002)
        for (u, v) in SUB_TOGGLES:
            toggle(m, cz + X_ * ((u - 0.5) * w_) + PU * ((v - 0.5) * sp_h), n, -PU, lever=0.016)   # painted levers point down
    # centre column: three ISIS standby displays between the main displays (cockpit_gauges, atlas cells 0, 1, 2)
    isis = {}
    for (z, cell) in ((0.835, 0), (0.745, 1), (0.655, 2)):
        w = 0.062
        h = w * 0.86
        uvs = [C3.cell_uv(cell, -1, -1), C3.cell_uv(cell, 1, -1), C3.cell_uv(cell, 1, 1), C3.cell_uv(cell, -1, 1)]
        small = MeshBuf()
        cs = small_screen(m, C3.panel_pt(0.0, z), X_, PU, w, h, small, side=0.008, lift=-0.004)   # frame front 9 mm proud, face 5 mm (main display faces 6 mm)
        oriented_quad(gf, cs, 'gauges', PN, uvs)
        isis[cell] = (sum(cs, V((0, 0, 0))) / 4, w, h)
    isis_movers = isis_184(gf, isis)
    # placard + master-mode push buttons under the ISIS column
    art_plate(m, C3.panel_pt(0.0, 0.585), X_, PU, 0.060, 0.037, 'placard_data', depth=0.006, proud=0.004)
    # 0.3.2 fix pass: the panel columns outboard of the two bezels (x 0.605 .. 0.655) carry single sub-panels cut from the
    # sub-panel strip art (HUD / MFD BRT / LIGHTS / STBY), with modelled knobs and toggles: no flat grey slab on the panel face
    OUT_X0, OUT_X1 = 0.605, 0.655
    cw = OUT_X1 - OUT_X0
    # 1.9.14: each crop's modelled control sits on its painted one (SUB_KNOBS / SUB_TOGGLES); 1.9.13 put a toggle on the ALT
    # knob crop and centred the knob beside the painted HUD knob
    # 1.9.14 in-game round: crops are WHOLE painted panels (the 0.00-0.13 HUD crop read "HUI" / "A-/" in game), each with all of
    # its controls: HUD (MODE + BRT knobs), ALT (baro knob), LIGHTS (LDG + TAXI toggles). Panel edges measured on subpanel_strip.png.
    crops = [((0.000, 0.229), [('knob', SUB_KNOBS[0]), ('knob', SUB_KNOBS[1])]),
             ((0.328, 0.468), [('knob', SUB_KNOBS[4])]),
             ((0.468, 0.636), [('toggle', SUB_TOGGLES[0] + (0.0,)), ('toggle', SUB_TOGGLES[1] + (0.0,))])]
    zcs, ztop = [], COLUMN_TOP_Z                          # round 4: stacked down from COLUMN_TOP_Z (LIGHTS clear of the console)
    for (u0, u1), _ in crops:
        ch = cw / ((u1 - u0) * LY.aspect('subpanel'))
        zcs.append(ztop - ch * PU.z / 2)
        ztop -= ch * PU.z + COLUMN_GAP
    for s_ in (-1, 1):
        xc = s_ * (OUT_X0 + OUT_X1) / 2
        for k, ((u0, u1), ctrls) in enumerate(crops):
            ch = cw / ((u1 - u0) * LY.aspect('subpanel'))
            zc = zcs[k]
            art_plate(m, C3.panel_pt(xc, zc), X_, PU, cw, ch, 'subpanel', depth=0.010, proud=0.006, sub=(u0, 0.0, u1, 1.0))
            for kind, (fu, fv, fr) in ctrls:
                base = C3.panel_pt(xc, zc) + PN * 0.0065 + X_ * (((fu - u0) / (u1 - u0) - 0.5) * cw) + PU * ((fv - 0.5) * ch)
                lo_ = SUB_KNOB_LOW.get(SUB_KNOBS.index((fu, fv, fr))) if kind == 'knob' else None
                if lo_:                                    # round 7: HUD MODE / BRT low tapered discs (SUB_KNOB_LOW)
                    knob(m, base, PN, r=fr * ch, h=lo_[1], top=lo_[2], ptr=lo_[3])
                elif kind == 'knob':
                    knob(m, base, PN, r=fr * ch, h=0.007)
                else:
                    toggle(m, base, PN, -PU, lever=0.010)
    g = P.Part('cockpit_gauges', 'fus_cockpit', (0, S.PANEL_Y, 0.70), gf,
               info=dict(note='ISIS standby displays (attitude, engine/power, nav/clock) stacked in the centre column; own UVs in the GA-25X gauge atlas'))
    g.own_uv = True
    parts.append(g)
    parts.extend(isis_movers)
    # caution lights on top of the glareshield (MASTER CAUTION amber + FIRE red cells of the annunciator art), both crew
    for x in (-0.13, 0.13):
        # 1.9.14: crops measured on annunciator.png (MASTER CAUTION frame u 0.044-0.106, FIRE R 0.586-0.646, frames v 0.30-0.95);
        # the old crops (0.012-0.072, v 0.12-0.88) cut the cells in half ("MAS CAU" in game). Quad keeps the cell aspect (~0.84).
        for k, (u0, u1) in enumerate(((0.044, 0.106), (0.586, 0.646))):
            c = V((x + (k - 0.5) * 0.050, LIP_Y + 0.045, GZ + 0.022))
            uy_ = V((0, math.sin(math.radians(30)), math.cos(math.radians(30))))
            obox_open(m, c - (X_.cross(uy_)) * 0.006, X_, uy_, (0.040, 0.044, 0.024), 'ck_black')
            n_ = X_.cross(uy_)
            if n_.y > 0:
                n_ = -n_
            art_quad(m, c + n_ * 0.0065, X_, uy_, 0.034, 0.038, 'annunciator', u0, 0.30, u1, 0.95)

    # ---------------------------------------------------------------- HUD (pilot): flush projector + thin combiner frame (no glass pane)
    gx = S.CREW['pilot']['eye'][0]
    gs = MeshBuf()
    box(gs, (gx, 4.27, GZ + 0.022), (0.13, 0.12, 0.026), 'ck_black')
    cmb = MeshBuf()
    cq = Quaternion(X_, math.radians(-25))
    cc = V((gx, 4.22, GZ + 0.085))
    hw, hh = 0.065, 0.050
    corners = [cc + cq @ V(p) for p in ((-hw, 0, -hh), (hw, 0, -hh), (hw, 0, hh), (-hw, 0, hh))]
    for a, b in zip(corners, corners[1:] + corners[:1]):
        cylinder(cmb, a, b, 0.0035, N=6, mat='ck_black')
    for s in (-1, 1):
        cylinder(gs, V((gx + s * hw, 4.24, GZ + 0.030)), corners[0 if s < 0 else 1], 0.0035, N=6, mat='ck_black')
    parts.append(P.Part('gunsight_pilot', 'fus_cockpit', (gx, 4.27, GZ + 0.022), gs, info=dict(note='HUD projector (flush on the glareshield)')))
    parts.append(P.Part('gunsight_combiner', 'gunsight_pilot', cc, cmb, info=dict(kind='combiner', note='HUD combiner frame (the game draws the HUD)')))

    parts.insert(0, P.Part('cockpit_interior', 'fus_cockpit', (0, 3.45, floor_z()), m,
                           info=dict(note='0.3.2 cockpit: tub with deep footwells, panel with bezelled displays and switch strips, '
                                          'glareshield + annunciators, side consoles, breaker panels, arc throttle quadrant pedestal, '
                                          'stick mounts. Panel art = ck_art (fal atlas). Stock seat / stick / throttle by the generator.')))
    return parts
