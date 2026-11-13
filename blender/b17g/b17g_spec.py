"""B-17G Flying Fortress: every number of the model (Phase B milestone 1, 2026-11-03).

Blender frame: nose +Y, up +Z, right wing +X, metres, real size. Stations are our own numbers: real B-17G dimensions, with
proportions MEASURED (numbers only) on the War Thunder reference outside the repo (nuclearoption-ref/study/b17g/measure, scale
31.62 / 31.258). No WT geometry, UV or texture is used. docs/b17g_design.md has the reasoning.
"""
import math

SPAN = 31.62
LENGTH = 22.66

# ---------------------------------------------------------------- fuselage: (y, top z, bottom z, half width, superellipse n)
FUS = [
    # bulbous plexiglass nose (M1 review): superellipse profile p 1.5 from the 6.55 station to the tip 7.45, centre rising to z 0.57
    *[(6.55 + 0.90 * t, 0.42 + 0.15 * t + 0.78 * max(1 - t ** 1.5, 0.0004) ** (1 / 1.5), 0.42 + 0.15 * t - 0.78 * max(1 - t ** 1.5, 0.0004) ** (1 / 1.5),
       0.80 * max(1 - t ** 1.5, 0.0004) ** (1 / 1.5), 2.2) for t in (0.995, 0.97, 0.92, 0.85, 0.76, 0.65, 0.52, 0.38, 0.24, 0.12)],
    (6.55, 1.20, -0.36, 0.80, 2.2),
    (6.10, 1.33, -0.55, 0.98, 2.3),
    (5.60, 1.44, -0.68, 1.07, 2.4),
    (5.00, 1.52, -0.72, 1.12, 2.5),     # split nose | cockpit
    (4.55, 1.62, -0.72, 1.15, 2.5),
    (4.15, 1.88, -0.72, 1.16, 2.6),     # windscreen
    (3.75, 2.02, -0.72, 1.165, 2.6),
    (2.90, 2.03, -0.72, 1.165, 2.6),    # split cockpit | centre
    (2.30, 2.02, -0.72, 1.165, 2.6),
    (1.75, 2.02, -0.72, 1.165, 2.6),    # bomb bay front
    (0.30, 2.01, -0.71, 1.165, 2.6),
    (-1.15, 1.97, -0.71, 1.165, 2.6),   # bomb bay rear
    (-1.60, 1.94, -0.71, 1.16, 2.6),    # split centre | radio
    (-2.40, 1.88, -0.69, 1.155, 2.6),
    (-3.20, 1.80, -0.63, 1.15, 2.6),    # split radio | waist
    (-4.00, 1.70, -0.52, 1.13, 2.5),
    (-5.00, 1.64, -0.44, 1.12, 2.5),
    (-6.20, 1.60, -0.37, 1.07, 2.4),
    (-7.40, 1.56, -0.30, 1.01, 2.4),
    (-8.60, 1.52, -0.23, 0.95, 2.3),    # split waist | tail
    (-9.60, 1.50, -0.10, 0.86, 2.3),
    # 1.7.8 (in-game 1.7.7: the tail read as a fat can with a flat round end): from -10.8 aft the stations follow the reference
    # sections (numbers only, nuclearoption-ref/study/b17g: triangle-plane sections of the WT mesh): a wider, lower body that keeps
    # tapering to the gunner's compartment (hw 0.84 -> 0.47) with the fin-root fairing pinched narrow above it (TAIL_PINCH), and
    # an end that rounds over onto the Cheyenne cover instead of flaring around it (1.7.7 was hw 0.40 / bottom 0.34 at -13, flared
    # to 0.42 at the end, full height to the end ring: the blunt can)
    (-10.80, 1.62, -0.12, 0.84, 2.4),
    (-12.00, 1.70, -0.06, 0.77, 2.6),
    (-13.00, 1.71, 0.04, 0.68, 2.6),    # split tail | tail gun
    (-14.00, 1.71, 0.17, 0.59, 2.6),
    (-14.40, 1.71, 0.22, 0.55, 2.6),
    # 1.7.9 (coordinator review of the 1.7.8 pairs: flat top to the end, then a vertical box end with the cover a small knob low on
    # it): reference sections -14.75..-15.2 (numbers only): body hw 0.50 / 0.48 / 0.45 at -14.75 / -14.80 / -14.85, the fin-root
    # fairing's top 1.71 -> 1.65 -> 1.38 -> 1.12 at -14.75 / -14.80 / -14.85 / -14.90, then only the cover (0.8 m tall at -14.90,
    # hw 0.35 at -15.00, its tip at -15.15). The end now slopes down onto the cover and the body stops at the opening.
    (-14.66, 1.71, 0.26, 0.52, 2.6),
    (-14.76, 1.70, 0.27, 0.50, 2.6),
    (-14.84, 1.48, 0.29, 0.46, 2.5),
    (-14.90, 1.24, 0.32, 0.42, 2.4),
    (-14.94, 1.16, 0.40, 0.36, 2.3),    # the end ring; the skin is cut by the opening (b17g_detail.tail_cut)
]
FUS_N = 40                       # points per ring
# 1.7.8 fin-root pinch of the aft fuselage section: (y, weight, neck z, cap half width). Above the neck the superellipse's half
# width is blended (s = 1 - (1 - t)^2, t = (z - neck) / (top - neck)) toward min(x, cap): a wide gunner's compartment under a
# narrow fairing that carries the fin and rudder (reference: hw 0.66 at z 0.9, 0.45 at 1.3, 0.28 at 1.5, 0.22 at 1.7 at y -13)
TAIL_PINCH = [(-9.60, 0.0, 1.30, 0.32), (-10.80, 1.0, 1.30, 0.30), (-12.00, 1.0, 1.15, 0.25), (-13.00, 1.0, 1.10, 0.22),
              (-14.00, 1.0, 1.05, 0.23), (-15.00, 1.0, 1.05, 0.23)]
SPLITS = [5.00, 2.90, -1.60, -3.20, -8.60, -13.00]
FUS_PARTS = ['fus_nose', 'fus_cockpit', 'B17G', 'fus_radio', 'fus_waist', 'fus_tail', 'tail_gun']   # B17G = root (centre)

# glazing zones on the fuselage skin (faces become 'glass'): (y0, y1, predicate on (x, z) at that y)
NOSE_GLASS_Y = 6.62              # plexiglass nose cone forward of this (frame bars on it); 1.8.17: 6.65 (NOSE1817 below)
WINDSCREEN = (3.85, 4.55)        # windscreen + cockpit side windows band
CABIN_WIN_Z = 1.35               # cockpit side windows above this z
RADIO_HATCH = (-3.45, -2.60)     # radio-room top hatch (open, gun); 1.8.13 r2/r3: -3.25 / -2.75 -> -3.45 / -2.60 (AN/M2 jacket aft, receiver forward at -25 deg)
WAIST_R = (-5.75, -4.60)         # staggered waist windows (B-17G): right forward
WAIST_L = (-7.25, -6.10)
WAIST_Z = (0.25, 1.15)
TAIL_WIN = (-14.40, -13.75)

# ---------------------------------------------------------------- wing (right side; mirrored)
WING_ROOT_X = 1.02               # inside the fuselage skin (embedded)
WING_TIP_X = SPAN / 2
WING_LE = [(1.02, 2.50), (1.40, 2.48), (4.40, 2.06), (8.00, 1.61), (11.00, 1.19), (14.00, 0.77), (14.74, 0.66), (15.30, 0.38), (15.62, -0.10), (15.81, -0.62)]
WING_TE = [(1.02, -3.26), (1.40, -3.25), (8.00, -2.65), (14.00, -2.05), (14.74, -1.97), (15.30, -1.78), (15.62, -1.32), (15.81, -0.82)]
WING_TC = [(1.02, 0.180), (4.75, 0.160), (8.90, 0.140), (14.74, 0.105), (15.81, 0.07)]
DIHEDRAL = 4.0                   # deg (measured 3.9, real 4.5)
WING_Z0 = 0.0                    # chord plane z at the root (low-mid wing, measured)
WING_INC = [(1.02, 3.0), (15.81, 1.0)]     # incidence deg (washout)
HINGE_F = 0.735                  # flap / aileron hinge at this chord fraction (measured flap chord 26 %, aileron 28 %)
WING_SPLITS = [4.75, 8.90, 14.74]          # wing_inner | wing_mid | wing_outer | wing_tip
FLAPS = [('flap_inner', 1.20, 4.75), ('flap_outer', 4.75, 8.80)]
AILERON = (8.95, 14.74)

# ---------------------------------------------------------------- engines / nacelles (right side; engines numbered 1-4 left to right)
# inner axis moved 5 cm outboard of the reference (3.05 -> 3.10) so the inner prop tip clears the fuselage by >= 15 cm
NACELLES = {   # name: (x axis, z axis, cowl lip y, prop plane y, cowl radius, nacelle end y, belly z)
    'inner': (3.10, 0.05, 4.33, 4.62, 0.78, -1.40, -0.74),     # round 5: the nacelles end 6 cm ahead of the flap hinge line (y -1.68 /
    'outer': (6.575, 0.30, 3.74, 4.02, 0.77, -1.30, -0.50),    # -1.57 at their axes) like the real aircraft (was -2.70 / -2.30: through the flaps)
}
BREAK183 = True                  # 1.8.3 wing split caps: a structure rib web in front of the paint cap, 4 cm in from the skin (break faces show structure)
NAC183 = True                    # 1.8.3 nacelles (b17g_nacelle.py: cowl ring + flaps, well opening, turbos, LE intakes); False = 1.8.2
# 1.8.8 (user 2026-11-08: 'THE ENGINE HOUSINGS ARE STILL WRONG ... compare the length of the engine houses for all 4 engines'): behind
# the wing leading edge the nacelle body is shaped RELATIVE TO OUR WING (depth below / height above the local wing skin and footprint
# width, measured on the reference: b17g_nacelle.B188). Our wing sits 0.10-0.15 m higher on the fuselage than the reference's while the
# nacelle axes match it to 5 mm, so the 1.8.3 absolute lines ran 0.6-0.8 m (outer) / 0.15 m (inner) too far aft before meeting the
# skin. Outer: pointed tail ending y -0.18; inner: flat squared fairing ending y -1.02. False = the 1.8.3 bodies.
NAC188 = True
PROP_R = 1.765                   # Hamilton Standard 3-blade, 11 ft 7 in
PROP_BLADES = 3
ENGINE_NUM = {(-1, 'outer'): 1, (-1, 'inner'): 2, (1, 'inner'): 3, (1, 'outer'): 4}
# 1.7.8 handed props (Unity turnDirection): the left pair as before (clockwise from behind), the right pair the other way with
# mirrored blades, so the four props put no net torque on the airframe (the FBW roll trim that held it caused the hands-off spiral;
# docs/b17g_design.md 18). The real R-1820s all turned clockwise: a deliberate deviation.
PROP_TURN = {1: 1, 2: 1, 3: -1, 4: -1}

# ---------------------------------------------------------------- main gear (forward-retracting into the inner nacelle, wheel half exposed)
WHEEL_R, WHEEL_W = 0.711, 0.50    # 56 in tyre
MAIN_X = 3.22                     # wheel plane x (measured 3.185 x 1.0115)
MAIN_PIVOT = (1.60, -0.52)        # (y, z) trunnion inside the nacelle behind the firewall
MAIN_LEG = 1.38                   # pivot -> axle height when down: axle z -1.90
MAIN_RAKE = 0.25                  # round 3 (nose-over margin, coordinator target >= 3 deg over the brake friction angle): the down leg is
                                  # raked 10.4 deg forward, the ground contact sits 0.25 m further ahead of the CoM; the stow is unchanged
MAIN_FOLD = 90.0 - __import__('math').degrees(__import__('math').atan2(0.25, 1.38))   # 79.7 deg: stowed axle (y 2.98, z -0.51) as before
# ---------------------------------------------------------------- tail wheel (retracts up and aft into the tail cone)
TAIL_WHEEL_R, TAIL_WHEEL_W = 0.33, 0.20
TAIL_PIVOT = (-9.05, 0.10)
TAIL_AXLE_DOWN = (-9.95, -0.52)
TAIL_FOLD = 27.0                  # deg
TAIL_WELL = (-10.50, -8.85)

# ---------------------------------------------------------------- tail surfaces
STAB_Z = 1.05
STAB_LE = [(0.30, -9.95), (1.40, -9.95), (6.00, -11.05), (6.45, -11.40), (6.62, -11.85)]
STAB_TE = [(0.30, -12.92), (1.40, -12.90), (6.00, -12.60), (6.45, -12.45), (6.62, -12.10)]
ELEV_HINGE_Y = -11.72             # straight hinge (measured elevator LE)
STAB_TC = 0.11
FIN_LE = [(1.45, -9.20), (2.40, -9.45), (3.10, -10.47), (3.70, -10.98), (4.30, -11.28), (4.90, -11.61), (5.25, -11.95), (5.44, -12.35)]
FIN_TE = [(1.45, -14.36), (2.40, -14.20), (3.70, -13.95), (4.60, -13.74), (5.20, -13.30), (5.44, -12.75)]
RUDDER_HINGE_Y = -12.78
FIN_TC = 0.12
DORSAL = [(-5.40, 1.64), (-7.50, 1.95), (-9.20, 2.40)]   # dorsal fillet top line (y, z) into the fin LE

# ---------------------------------------------------------------- bomb bay (lengthened to 2.95 m for the 2.7 m GPO-500)
BAY_Y = (-1.15, 1.80)
BAY_HALF_W = 1.00                 # door opening half width at the belly
BAY_ROOF_Z = 1.32
HP_BOMBBAY = (0.0, 0.33, 0.62)    # hardpoint (x, y, z); stock mounts hang below it
CATWALK_Z = (-0.47, -0.41)        # narrow keel beam low in the bay, under every stock store
CATWALK_HALF_W = 0.03
# stock store envelopes relative to the hardpoint (x0, x1, y0, y1, z0, z1): measured on the stock mount prefabs (stock.py tree) + bomb sizes
STORES = {
    'bomb_250_internalx8 (8 x PAB-250)': (-0.75, 0.75, -1.125, 1.125, -0.47, 0.17),
    'bomb_500_internalx4_stack (4 x GPO-500)': (-0.50, 0.50, -1.35, 1.35, -0.605, 0.295),
    'bomb_cluster1_dual_internal (2 x CBO-400)': (-0.40, 0.40, -1.35, 1.35, -0.40, 0.05),
    'nuclearBomb1_internal (GPO-N)': (-0.25, 0.25, -1.35, 1.35, -0.40, 0.10),
}

# ---------------------------------------------------------------- defensive positions (numbers measured on the reference; az/el frames ours)
# name: dict(pos = pivot (x,y,z), fwd = rest direction, guns = [(dx, dz) offsets across the pivot], barrel length, limits, cones)
# 1.8.0 (user: "the tail turret has no front window for the gunner"): the Cheyenne gun cover now fills only the lower part of the end
# opening (centre z 0.72 -> 0.61, vertical radius 0.42 -> 0.31: z 0.30..0.92) and the gunner's aft window is glazed above it, between the
# cover and the opening's top (b17g_detail.tail_lip), at his eye height (tail eye z 1.15, b17g_cockpit). The guns and the az / el pivots move
# down with the cover. False = the 1.7.9 cover (0.8 m tall, no window).
TAIL_WINDOW = True
# 1.8.8 (user 2026-11-08: 'tail, tail windows and tail turret do not match the reference at all'): the gunner's glazed cab on the tail end
# (side panes 1.13-1.64 m with a post, small forward window, the sloped aft face above the opening glazed = the gunner's aft window), the
# square side window gone, and the Cheyenne cover at the reference size and height (centre z 0.70, radii 0.46 / 0.36: z 0.34..1.06,
# tip y -15.16; reference z 0.34..1.06, tip -15.17). The guns and az / el pivots move up with it. False = the 1.8.0 tail.
TAIL188 = True
# 1.8.13 round 2 (offline L): the gun slots of the chin / top / tail bodies go THROUGH (no back wall; side and end walls kept, the body
# lined inside) so the AN/M2 jackets pass through them and the receivers sit inside; slot lengths cover the elevation sweep
ANM2_SLOTS = True
CHEEK_TRAV = 15.0 if ANM2_SLOTS else 30.0     # r2: +-30 -> +-15 about the WT rest aim 33 deg: with the receiver 0.25 m inside the socket its outboard
                                              # side meets the nose wall when the gun turns inboard of ~16 deg from straight ahead
RADIO_EMIN = -25.0      # r2: kept (the hatch opening is lengthened aft instead, RADIO_HATCH)
TAIL_GUN_Z = 0.70 if TAIL188 else (0.61 if TAIL_WINDOW else 0.72)
# cab glazing stations (y): small forward window, main side pane, post, aft side pane (aft of the post to the end, + the sloped aft face)
TAIL_CAB = dict(small=(-14.00, -13.74), main=(-14.62, -14.09), post=(-14.71, -14.62), aft_face=-14.76, z_top=1.64, z_small=1.31, z_sill=1.13)
TURRETS = {
    # round 5: guns where the real turrets carry them (ref: chin x +-0.27-0.29 at z -0.74, top +-0.33, ball +-0.2, tail +-0.13)
    # 1.8.13 r2: chin +-0.234 (WT) / top +-0.15 (at +-0.27 / +-0.30 the AN/M2 receiver corners stood out of our round drum / dome; the top
    # guns sit under the dome's crown so the receivers clear it at 85 deg)
    'chin':  dict(pos=(0.0, 6.14, -0.74), fwd=(0, 1, 0), guns=[(-0.234, 0.0), (0.234, 0.0)] if ANM2_SLOTS else [(-0.27, 0.0), (0.27, 0.0)], station='Chin', trav=78.0 if ANM2_SLOTS else 86.0,   # r4: 86 -> 78 (at +-86 / +20 the jacket met the nose underside)
    emin=-26.0, emax=20.0),
    'top':   dict(pos=(0.0, 2.08, 2.12), fwd=(0, 1, 0), guns=[(-0.15, 0.0), (0.15, 0.0)] if ANM2_SLOTS else [(-0.30, 0.0), (0.30, 0.0)], el_dz=0.0, station='Top', trav=360.0, emin=0.0, emax=85.0),
    'ball':  dict(pos=(0.0, -3.95, -0.80), fwd=(0, 1, 0), guns=[(-0.20, 0.0), (0.20, 0.0)], station='Ball', trav=360.0, emin=-90.0, emax=0.0),
    'tail':  dict(pos=(0.0, -14.70, TAIL_GUN_Z), fwd=(0, -1, 0), guns=[(-0.13, 0.0), (0.13, 0.0)], station='Tail', trav=30.0, emin=-30.0, emax=30.0),
    # 1.8.13 r2: cheek rest aims from the WT reference guns (31-33 deg outboard; were 20): at 20 deg the receivers lay along the nose wall
    'cheek_R': dict(pos=(1.04, 5.90, 0.62), fwd=(0.53, 0.848, 0) if ANM2_SLOTS else (0.34, 0.94, 0), guns=[(0.0, 0.0)], station='Flexible', trav=CHEEK_TRAV, emin=-20.0, emax=20.0),
    'cheek_L': dict(pos=(-0.88, 6.40, 0.64), fwd=(-0.53, 0.848, 0) if ANM2_SLOTS else (-0.34, 0.94, 0), guns=[(0.0, 0.0)], station='Flexible', trav=CHEEK_TRAV, emin=-20.0, emax=20.0),
    'waist_R': dict(pos=(0.92, -5.17, 0.70), fwd=(1, 0, 0), guns=[(0.0, 0.0)], station='Flexible', trav=55.0, emin=-40.0, emax=50.0),
    'waist_L': dict(pos=(-0.86, -6.70, 0.70), fwd=(-1, 0, 0), guns=[(0.0, 0.0)], station='Flexible', trav=55.0, emin=-40.0, emax=50.0),
    'radio': dict(pos=(0.0, -3.00, 1.78), fwd=(0, -0.5, 0.866), guns=[(0.0, 0.0)], station='Flexible', trav=30.0, emin=RADIO_EMIN, emax=25.0),   # r2: emin -25 -> -5 (the barrel meets the hatch coaming / frame below -5)
}
GUN_LEN = 1.65                    # M2 overall (stock barrel mesh fits the gun slot in Unity)

# ---------------------------------------------------------------- 1.8.17 nose to the reference (user: the nose does not match the WT B-17G)
# Measured on the WT B-17G-60-VE in this frame (numbers only; ray-cast maps in nuclearoption-ref/study/b17g_nose/measure):
# - glazed cone: base ring y 6.65-6.67 (top 1.176 / bottom -0.30 / half width 0.711), tip y 7.43-7.44 at z 0.56; centreline top 1.132 /
#   1.037 / 0.919 / 0.801 / 0.685 and bottom -0.26 / -0.057 / 0.170 / 0.338 / 0.448 at y 6.75 / 6.95 / 7.15 / 7.30 / 7.40; half width
#   0.652 / 0.528 / 0.393 / 0.274 / 0.162 (ours 1.8.16: a bulbous dome from 6.62, up to 0.10 m wider, bottom 0.07-0.10 lower)
# - nose skin narrower ahead of the cockpit: half width at z 0.4: 1.016 / 0.899 / 0.806 at y 5.6 / 6.1 / 6.4 (ours 1.068 / 0.978 / 0.858)
# - no frame bars on the cone: a frame ring at its base, the optical flat (framed trapezoid) low at the front; glass down to the chin turret
# - windows (rounded rectangles, y0 y1 z0 z1): navigator both sides 4.67-5.06 x 0.50-0.81, left 5.27-5.66 x 0.50-0.81, right forward
#   6.12-6.51 x 0.50-0.77; top window 6.12-6.50 x +-0.15; astrodome r 0.20 at y 5.38, top z 1.688; K-5 cheek frames: right pane
#   5.18-5.76 x 0.47-1.05, front panes 5.82-5.94, gun line 33 deg through (0.99, 5.886, 0.59); left pane 6.05-6.45 x 0.51-1.02, front
#   panes 6.49-6.60, gun line 35 deg through (-0.78, 6.563, 0.64); front faces 42 / 28 deg outboard of forward; panes stand out
#   0.08-0.11 m at their front edges
# - chin: drum r 0.49 at y 6.14 (= ours); keel fairing from y ~4.5 to the drum, keel z -0.737 / -0.784 / -0.827 / -0.846 at 4.6 / 5.0 /
#   5.4 / 5.6; a mast with a fore-aft rod on the nose top at y 6.07 (top z 1.68, rod 5.62-6.10)
# False = the 1.8.16 nose.
NOSE1817 = True
if NOSE1817:
    _NOSE_ROWS = [
        (7.435, 0.600, 0.520, 0.055, 2.0),      # tip ring (glass fan cap)
        (7.40, 0.685, 0.448, 0.162, 2.0),
        (7.35, 0.753, 0.388, 0.232, 2.1),
        (7.30, 0.801, 0.338, 0.274, 2.1),
        (7.25, 0.844, 0.283, 0.314, 2.1),
        (7.15, 0.919, 0.170, 0.393, 2.2),
        (7.05, 0.984, 0.057, 0.464, 2.2),
        (6.95, 1.037, -0.057, 0.528, 2.2),
        (6.85, 1.086, -0.170, 0.591, 2.2),
        (6.75, 1.132, -0.260, 0.652, 2.2),
        (6.70, 1.154, -0.284, 0.682, 2.2),
        (6.65, 1.176, -0.300, 0.711, 2.2),      # glass base ring (NOSE_GLASS_Y)
        (6.40, 1.259, -0.420, 0.800, 2.25),
        (6.10, 1.345, -0.550, 0.900, 2.3),
        (5.60, 1.460, -0.680, 1.030, 2.4),
    ]
    FUS = _NOSE_ROWS + [r for r in FUS if r[0] <= 5.00 + 1e-9]
    NOSE_GLASS_Y = 6.65
    NOSE1817_WINDOWS = [
        # navigator windows: reference 4.67-5.06 crosses our 5.00 split: kept whole in fus_cockpit, 9-12 cm aft (4.58-4.94)
        dict(part='fus_cockpit', kind='side', side=1, rect=(4.58, 4.94, 0.50, 0.81), rc=0.06, tag='nav_R'),
        dict(part='fus_cockpit', kind='side', side=-1, rect=(4.58, 4.94, 0.50, 0.81), rc=0.06, tag='nav_L1'),
        dict(part='fus_nose', kind='side', side=-1, rect=(5.27, 5.66, 0.50, 0.81), rc=0.06, tag='nav_L2'),
        dict(part='fus_nose', kind='side', side=1, rect=(6.12, 6.51, 0.50, 0.77), rc=0.06, tag='fwd_R'),
        dict(part='fus_nose', kind='top', rect=(6.12, 6.50, -0.15, 0.15), rc=0.05, tag='top_win'),
        dict(part='fus_nose', kind='dome', cy=5.38, r=0.20, h=0.16, tag='astrodome'),
    ]
    NOSE1817_K5 = [
        dict(tag='k5_R', side=1, pivot=(0.99, 5.886, 0.59), face_deg=42.0, y_a=5.18, y_f=5.78, z0=0.47, z1=1.05, drop=0.18, rise=0.06,
             plate_up=0.10, hole_r=0.070, y_max=5.98),
        dict(tag='k5_L', side=-1, pivot=(-0.78, 6.563, 0.64), face_deg=28.0, y_a=6.05, y_f=6.49, z0=0.51, z1=1.02, drop=0.16, rise=0.05,
             plate_up=0.10, hole_r=0.070, y_max=6.615),
    ]
    NOSE1817_FLAT = dict(bottom=(6.84, -0.18, 0.07), top=(7.28, 0.32, 0.20))
    NOSE1817_CHIN_HOLE_R = 0.50          # exact round opening (drum r 0.475, 0.491 on its diagonals); was a 0.57 face-wise cut + sloped fairing
    NOSE1817_CHIN_HOLE_YMAX = 6.61       # flat front edge just ahead of the drum (6.596): the glass base ring at 6.65 stays whole
    NOSE1817_KEEL = dict(y0=4.52, L=1.08, d=0.165, w=0.45, ex=1.1, m=5.0, y_front=5.85, r_drum=0.505)   # front 5.85 at the sides: the aft chin gun at az +-86 / el +20 passes at y 5.91
    NOSE1817_MAST = dict(y=6.06, top_z=1.66, rake=0.03, chord=0.07, thick=0.022, rod=(5.62, 6.10))
    # cheek gun pivots on the K-5 sockets (reference gun lines); rest aims / traverse unchanged unless the sweep allows more
    TURRETS['cheek_R']['pos'] = NOSE1817_K5[0]['pivot']
    TURRETS['cheek_L']['pos'] = NOSE1817_K5[1]['pivot']
    # limits the new nose allows (Unity AN/M2 sweep 0 clipping poses, fire-clearance 0 blocked cells; unitylogs\p1817t3_clear.log,
    # p1817t3_build.log): chin back to the historical +-86 (the 1.8.13 r4 cut to +-78 was the jacket against the sloped chin fairing, now
    # gone; the keel fairing ends at y 5.85 at its sides so the aft gun passes at az +-86 / el +20, min 5 mm); cheeks +-15 -> +-20 about the
    # same 32 deg rest aim (receiver inside the projecting K-5 wedge, min 25 / 31 mm; +-25 and more not swept)
    TURRETS['chin']['trav'] = 86.0
    TURRETS['cheek_R']['trav'] = TURRETS['cheek_L']['trav'] = 20.0

# 1.8.18 (in game 1.8.17, close up): two build-time fixes on the B-17G nose; False = the 1.8.17 output (release path, stub-tested).
# GLARE_AA1818: the NM anti-glare panel edges ramp over +-1.25 texel in metres at the same place (the rounded front was a hard per-texel
#   step: saw-tooth), metal map follows the coverage (build_textures_b17g.livery).
# DOME_RING1818: the astrodome's inner frame is one continuous ring (was 40 separate chord blocks with wedge gaps and 1.5 mm alternating
#   steps: jagged dark / light teeth from inside) and the nose frames / stringers stop on that ring with closed ends (they ended open,
#   10 cm short of it); the outside (skin, cut, glass dome, the outer paint ring) is unchanged (b17g_nose1817.astrodome_body, b17g_detail).
GLARE_AA1818 = NOSE1817 and True
DOME_RING1818 = NOSE1817 and True
DOME_RING1818_SECTION = dict(r_in=0.180, r_out=0.220, d_top=0.004, d_bot=0.028, n=48, r_stop=0.216)

# ---------------------------------------------------------------- budgets
TRI_BUDGET_TOTAL = 200000            # 1.8.3: + nacelles (cowl flaps, well, turbos, LE intakes) ~ +27k; was 185000
TRI_BUDGET_PREV = 185000            # round 5: + internals (spars, ribs, fuel cells, frames, stringers, engines, turbos); B-25H 77k / cockpit cost unmeasurable in game
TRI_BUDGET_EXTERIOR = 110000
if NOSE1817:
    TRI_BUDGET_TOTAL = 215000        # 1.8.17: + nose windows / K-5 frames / astrodome / keel fairing / exact cuts ~ +11k (1.8.16: 199,909)


def interp(table, x):
    if x <= table[0][0]:
        return table[0][1]
    for (x0, v0), (x1, v1) in zip(table, table[1:]):
        if x <= x1:
            t = (x - x0) / (x1 - x0)
            if isinstance(v0, tuple):
                return tuple(a + (b - a) * t for a, b in zip(v0, v1))
            return v0 + (v1 - v0) * t
    return table[-1][1]


def fus_pinch(y, x, z, inset=0.0):
    """x of a fuselage section point after the fin-root pinch (TAIL_PINCH); unchanged forward of -9.6 or below the neck."""
    xp = _pinch178(y, x, z, inset)
    if TAIL188 and y < -13.0:
        # 1.8.8: the gunner's cab (reference sections y -13.5..-14.7: hw 0.35 at z 1.18, 0.31 at 1.34, 0.27 at 1.50, 0.23 at 1.66 above a
        # shoulder at z ~1.1): straight tapering cab sides (cap 0.37 at the neck z 1.02 -> 0.22 at the top) reached quickly above the
        # shoulder (blend 1 - (1 - t)^6); faded in from the -13.0 split (rings there unchanged) to -13.5
        top = fus_station(y)[0] - inset
        zn2 = 1.02 - inset
        alt = x
        if z > zn2 and top > zn2:
            t2 = min((z - zn2) / (top - zn2), 1.0)
            s2 = 1.0 - (1.0 - t2) ** 6
            cap2 = 0.37 - 0.15 * t2 - inset
            alt = x * (1.0 - s2) + math.copysign(min(abs(x), max(cap2, 0.01)), x) * s2
        r = min((-13.0 - y) / 0.5, 1.0)
        xp = xp * (1.0 - r) + alt * r
    return xp


def _pinch178(y, x, z, inset=0.0):
    """the 1.7.8 fin-root pinch."""
    if y > TAIL_PINCH[0][0]:
        return x
    tab = sorted(TAIL_PINCH, key=lambda r: r[0])
    w = interp([(r[0], r[1]) for r in tab], y)
    if w <= 0.0:
        return x
    zn = interp([(r[0], r[2]) for r in tab], y); cap = interp([(r[0], r[3]) for r in tab], y) - inset
    top = fus_station(y)[0] - inset
    if z <= zn or top <= zn:
        return x
    t = min((z - zn) / (top - zn), 1.0)
    s_ = w * (1.0 - (1.0 - t) ** 2)
    return x * (1.0 - s_) + math.copysign(min(abs(x), max(cap, 0.01)), x) * s_


def in_pinch(p, margin=0.06):
    """True where the section is pinched (fin-root fairing) at p, from `margin` below the neck up: internals skip it (their straight
    bars and coarse chords would show through the concave shoulders)."""
    if p.y > TAIL_PINCH[0][0]:
        return False
    tab = sorted(TAIL_PINCH, key=lambda r: r[0])
    w = interp([(r[0], r[1]) for r in tab], p.y)
    return w > 0.0 and p.z > interp([(r[0], r[2]) for r in tab], p.y) - margin


def fus_station(y):
    """(top, bottom, half width, n) at y (linear between the station table)."""
    rows = sorted(FUS, key=lambda r: r[0])
    tab = [(r[0], (r[1], r[2], r[3], r[4])) for r in rows]
    return interp(tab, y)


def wing_chord(x):
    x = abs(x)
    le, te = interp(WING_LE, x), interp(WING_TE, x)
    return le, te


def wing_z(x):
    return WING_Z0 + (abs(x) - WING_ROOT_X) * math.tan(math.radians(DIHEDRAL))

# exclusion firing cones per position (world direction, half angle deg): own structure inside them (scan: check_b17g_model.py f)
TURRET_EXCLUDE = {}
