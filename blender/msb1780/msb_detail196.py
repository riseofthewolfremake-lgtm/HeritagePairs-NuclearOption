"""MSB-17/80 1.9.6 cockpit detail pass on OUR deck (msb_deck195; coordinator review of 1.9.5: "a grey board with six black holes"; the SFB-81
cockpit is the bar). Modelled controls only, no procedural textures: two greys + black from the deck materials, white backlit legends
('ck_legend', emissive white bars) and annunciator lamps ('ck_amber' / 'ck_green', dim emissive). Everything sits on our own parts; the stock
parts (sticks, throttle, lamps, seats) are untouched.

  panel        recessed screen wells (frame 26 mm deep, screen 13 mm behind the frame face), a raised centre stack (36 mm proud) carrying the
               attitude MFD, the standby display, the landing-gear lever (wheel knob, UP / DN legends) and the flap selector (four detents);
               caution / annunciator strips under the glare shield; rotary selectors, push-button strips and toggle rows with legends under
               the MFDs
  glare shield soft rolled visor edge (msb_deck195 profile) + a mode-control strip on its front face: windows and knobs between the lamps
  pedestal     throttle quadrant surround: centre spine on the gate with detent marks and IDLE / MAX legends, slot detents; aft extension with
               two radio / nav control heads; trim wheels recessed in its sides; speed-brake lever
  consoles     comm panel (volume knobs + push buttons), oxygen panel (flow blinker, supply lever), switch panel (toggles), map pocket
  overhead     breaker rows and switch rows on the 1.9.2 strip
Helpers place everything in a local frame (right, up, normal) of the surface it sits on.
"""
import math
from mathutils import Vector as V, Matrix
from b25h_geom import oriented_quad, cylinder, box, circle_pts, loft, fan_cap


def rot(right, up, n):
    """box() rotation: local x = right, y = n (depth), z = up."""
    return Matrix((right, n, up)).transposed().to_quaternion()


def plate(mb, c, right, up, n, w, h, d=0.004, mat='ck_black'):
    """thin plate w x h, d thick, its back face on the surface at c."""
    box(mb, tuple(c + n * (d / 2)), (w, d, h), mat, rot=rot(right, up, n))


def legend(mb, c, right, up, n, w=0.010, h=0.0022):
    """white backlit legend bar (a stand-in for printed text), 1.2 mm proud (beyond the 0.8 mm z-fight resolver, b17g_zfix)."""
    q = [c - right * (w / 2) - up * (h / 2), c + right * (w / 2) - up * (h / 2), c + right * (w / 2) + up * (h / 2), c - right * (w / 2) + up * (h / 2)]
    oriented_quad(mb, [p + n * 0.0012 for p in q], 'ck_legend', n)


def toggle(mb, c, right, up, n, lever=0.020):
    """toggle switch: boss + bat lever tipped toward `up`; a legend bar under it."""
    cylinder(mb, c, c + n * 0.005, 0.0055, N=8, mat='ck_bezel')
    tip = c + n * (0.005 + lever * 0.92) + up * (lever * 0.38)
    cylinder(mb, c + n * 0.004, tip, 0.0021, 0.0017, N=6, mat='ck_bezel', cap0=False)
    legend(mb, c - up * 0.013, right, up, n, 0.012, 0.0022)


def knob(mb, c, n, r=0.010, h=0.012, N=10):
    cylinder(mb, c, c + n * h, r, r * 0.88, N=N, mat='ck_black', cap0=False)


def rotary(mb, c, right, up, n, r=0.011, ticks=5):
    """rotary selector: knob with a white pointer bar on its face and position legends round it."""
    knob(mb, c, n, r, 0.013)
    legend(mb, c + n * 0.013 + up * (r * 0.45), right, up, n, 0.0022, r * 0.8)
    for k in range(ticks):
        a = math.radians(-60 + 120 * k / max(ticks - 1, 1))
        p = c + (up * math.cos(a) + right * math.sin(a)) * (r + 0.007)
        legend(mb, p, right, up, n, 0.004, 0.0022)


def pushbuttons(mb, c, right, up, n, k=5, pitch=0.022, w=0.017, h=0.012):
    """strip of k square push buttons on a black base, each with a backlit legend on its face."""
    plate(mb, c, right, up, n, pitch * k + 0.008, h + 0.010, 0.003, 'ck_black')
    for i in range(k):
        p = c + right * ((i - (k - 1) / 2) * pitch) + n * 0.003
        box(mb, tuple(p + n * 0.003), (w, 0.006, h), 'ck_bezel', rot=rot(right, up, n))
        legend(mb, p + n * 0.006, right, up, n, w * 0.6, 0.0025)


def annunciators(mb, c, right, up, n, k=6, w=0.040, h=0.016, amber=(1, 3)):
    """caution / annunciator strip: k lamp tiles in a black frame (dim amber / green), legend bar on each."""
    plate(mb, c, right, up, n, k * (w + 0.004) + 0.008, h + 0.010, 0.004, 'ck_black')
    for i in range(k):
        p = c + right * ((i - (k - 1) / 2) * (w + 0.004)) + n * 0.004
        q = [p - right * (w / 2) - up * (h / 2), p + right * (w / 2) - up * (h / 2), p + right * (w / 2) + up * (h / 2), p - right * (w / 2) + up * (h / 2)]
        oriented_quad(mb, [x + n * 0.0012 for x in q], 'ck_amber' if i in amber else 'ck_green', n)


def well(mb, c, right, up, n, w, h, bezel=0.032, depth=0.026, recess=0.013):
    """screen well: a frame (bezel wide) standing `depth` off the surface, the screen opening walled to `recess` behind the frame face,
    a black back plate at the screen plane. Returns the screen centre (on the plane where the screen quad goes)."""
    W, H = w + 2 * bezel, h + 2 * bezel
    f = c + n * depth                      # frame face plane
    s = c + n * (depth - recess)           # screen plane
    o = [(-W / 2, -H / 2), (W / 2, -H / 2), (W / 2, H / 2), (-W / 2, H / 2)]
    i = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
    P = lambda base, xy: base + right * xy[0] + up * xy[1]
    for k in range(4):                     # frame face (between outer and inner outline), outer walls, inner walls
        a, b = k, (k + 1) % 4
        oriented_quad(mb, [P(f, o[a]), P(f, o[b]), P(f, i[b]), P(f, i[a])], 'ck_black', n)
        oriented_quad(mb, [P(c, o[a]), P(c, o[b]), P(f, o[b]), P(f, o[a])], 'ck_panel', P(V((0, 0, 0)), ((o[a][0] + o[b][0]) / 2, (o[a][1] + o[b][1]) / 2)))
        oriented_quad(mb, [P(s, i[a]), P(s, i[b]), P(f, i[b]), P(f, i[a])], 'ck_black', -P(V((0, 0, 0)), ((i[a][0] + i[b][0]) / 2, (i[a][1] + i[b][1]) / 2)))
    oriented_quad(mb, [P(s - n * 0.001, x) for x in i], 'ck_black', n)
    return s


def softkeys(mb, f, right, up, n, w, h, bezel=0.032, side=True):
    """soft keys in the frame face f (bottom row, and four down each side of a full-height unit), each with a legend."""
    nk = 5 if w > 0.15 else 3
    R = rot(right, up, n)
    for k in range(nk):
        p = f + right * (-w / 2 + (k + 0.5) * w / nk) - up * (h / 2 + bezel / 2)
        box(mb, tuple(p + n * 0.003), (0.020, 0.006, 0.010), 'ck_bezel', rot=R)
        legend(mb, p + n * 0.006, right, up, n, 0.010, 0.002)
    if side and h >= 0.12:
        for sd in (-1, 1):
            for k in range(4):
                p = f + right * sd * (w / 2 + bezel / 2) - up * (h / 2) + up * ((k + 0.5) * h / 4)
                box(mb, tuple(p + n * 0.003), (0.010, 0.006, 0.018), 'ck_bezel', rot=R)


# ---------------------------------------------------------------------------------------------------- centre-stack controls
def gear_lever(mb, c, right, up, n):
    """landing-gear lever on the stack: a slotted plate, an arm out of the slot and the classic wheel knob, UP / DN legends."""
    plate(mb, c, right, up, n, 0.050, 0.090, 0.004, 'ck_black')
    oriented_quad(mb, [c + n * 0.0052 + right * sx * 0.004 + up * sy * 0.035 for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))], 'ck_panel', n)   # slot
    root = c + n * 0.004 + up * 0.020                                      # lever up (gear up)
    tip = root + n * 0.045 + up * 0.010
    cylinder(mb, root, tip, 0.0035, N=6, mat='ck_bezel', cap0=False)
    cylinder(mb, tip - right * 0.010, tip + right * 0.010, 0.014, N=12, mat='ck_legend')   # wheel knob (white)
    legend(mb, c + up * 0.040 + right * 0.016, right, up, n, 0.010, 0.0025)
    legend(mb, c - up * 0.040 + right * 0.016, right, up, n, 0.010, 0.0025)
    for k in range(3):                                                     # three gear lamps (green, flat lenses) beside it
        p = c - right * 0.016 + up * (-0.020 + 0.020 * k) + n * 0.0052
        fan_cap(mb, circle_pts(p, n, 0.004, 8), p, 'ck_green', n)


def flap_selector(mb, c, right, up, n):
    """flap selector: gate plate with four detents (legend bars) and a short lever with a flat (aerofoil-section) knob."""
    plate(mb, c, right, up, n, 0.050, 0.090, 0.004, 'ck_black')
    oriented_quad(mb, [c + n * 0.0052 + right * sx * 0.004 + up * sy * 0.035 for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))], 'ck_panel', n)
    for k in range(4):
        legend(mb, c + up * (0.030 - 0.020 * k) - right * 0.016, right, up, n, 0.008, 0.002)
    root = c + n * 0.004 + up * 0.010
    tip = root + n * 0.035
    cylinder(mb, root, tip, 0.003, N=6, mat='ck_bezel', cap0=False)
    box(mb, tuple(tip + n * 0.004), (0.026, 0.010, 0.012), 'ck_legend', rot=rot(right, up, n))


# ---------------------------------------------------------------------------------------------------- pedestal
def radio_head(mb, c, right, up, n, w=0.180, h=0.060):
    """radio / nav control head: black box with two small display windows (dark, legend digits) and two concentric knobs."""
    plate(mb, c, right, up, n, w, h, 0.010, 'ck_black')
    f = c + n * 0.010
    for sx in (-1, 1):
        p = f + right * (sx * w * 0.20)
        q = [p - right * 0.025 - up * 0.008, p + right * 0.025 - up * 0.008, p + right * 0.025 + up * 0.008, p - right * 0.025 + up * 0.008]
        oriented_quad(mb, [x + n * 0.0012 for x in q], 'ck_panel', n)
        for k in range(4):
            legend(mb, p - right * 0.015 + right * (0.010 * k) + up * 0.0, right, up, n, 0.006, 0.0025)
    for sx in (-1, 1):
        p = f + right * (sx * w * 0.42)
        knob(mb, p, n, 0.010, 0.010, N=10)
        knob(mb, p + n * 0.010, n, 0.006, 0.008, N=8)


def trim_wheel(mb, c, axis, r=0.055, t=0.014):
    """trim wheel standing in a slot of the pedestal side (axis = across the aircraft): rim + ribs, a white index mark."""
    a = V(axis).normalized()
    cylinder(mb, c - a * (t / 2), c + a * (t / 2), r, N=20, mat='ck_black')
    up = V((0, 0, 1))
    p = c + a * (t / 2 + 0.0012) + up * (r * 0.75)
    fwd = a.cross(up)
    q = [p - fwd * 0.002 - up * 0.008, p + fwd * 0.002 - up * 0.008, p + fwd * 0.002 + up * 0.008, p - fwd * 0.002 + up * 0.008]
    oriented_quad(mb, q, 'ck_legend', a)


# ---------------------------------------------------------------------------------------------------- consoles / overhead
def breakers(mb, c, right, up, n, cols=6, rows=2, pitch=0.026):
    """circuit-breaker rows: collars with white push heads."""
    for j in range(rows):
        for i in range(cols):
            p = c + right * ((i - (cols - 1) / 2) * pitch) + up * ((j - (rows - 1) / 2) * 0.026)
            cylinder(mb, p, p + n * 0.006, 0.0045, N=6, mat='ck_black', cap0=False)
            cylinder(mb, p + n * 0.006, p + n * 0.009, 0.0030, N=6, mat='ck_legend', cap0=False)
