"""B-25H cockpit rebuild (0.2 cockpit, 2026-11-01): shared layout of the main instrument panel and the panel-art atlas.

Pure Python (no bpy): imported by the cockpit generator (b25h_v3_cockpit.py), the atlas builder
(textures/make_cockpit_art_b25h.py) and the guide drawer (draw_guides()).

Panel face coordinates: x (m, + = right) and z (m, height) on the raked panel plane (b25h_v3_cockpit.panel_pt(x, z)).
REAL = dials that are objects (needles / cards driven by stock components or the B25H.Instruments plugin; names gauge_<id>).
DECO = painted 1940s dials in the fal panel art (static). MFDS = the 2082 retrofit screens (tac / target camera / tablets).
"""
# v3 (2026-11-01, pass 2): the B-25 main panel spans almost the cabin width with an ARCHED top under a rounded coaming
# (photos 44-49). The art covers PANEL_RECT; the geometry face is cut to the arch panel_top(x).
PANEL_RECT = (-0.655, 0.655, 0.47, 0.95)          # x0, x1, z0, z1 of the panel art (the face follows the arch below z1)
ARCH_HALF, ARCH_BASE, ARCH_P = 0.70, 0.66, 2.2    # panel_top(x) = BASE + (z1 - BASE) * (1 - (|x| / HALF)^P)^(1/P)


def panel_top(x):
    x0, x1, z0, z1 = PANEL_RECT
    t = min(abs(x) / ARCH_HALF, 0.999999)
    return ARCH_BASE + (z1 - ARCH_BASE) * (1.0 - t ** ARCH_P) ** (1.0 / ARCH_P)


# id, x, z, radius (m): REAL dials are objects (needles / cards driven in game). Pilot flight group in front of the pilot
# (x -0.36), engine group right of centre, as on the B-25J/H panels in the photos.
REAL = [('airspeed', -0.465, 0.822, .038), ('attitude', -0.36, 0.832, .042), ('altimeter', -0.255, 0.822, .040),
        ('fuel', -0.465, 0.718, .032), ('heading', -0.36, 0.722, .040), ('vsi', -0.255, 0.718, .034),
        ('manifold_L', 0.12, 0.835, .036), ('manifold_R', 0.215, 0.835, .036), ('rpm_L', 0.12, 0.735, .036), ('rpm_R', 0.215, 0.735, .036),
        ('oil_press', 0.31, 0.850, .025), ('oil_temp', 0.31, 0.780, .025), ('cyl_temp', 0.31, 0.710, .025),
        ('hydraulic', 0.39, 0.835, .025), ('flaps_pos', 0.39, 0.765, .025), ('gear_pos', 0.39, 0.695, .025)]
# painted 1940s dials (fal art), x, z, r
DECO = [(-0.575, 0.770, .025), (-0.575, 0.690, .024), (-0.115, 0.800, .022), (-0.020, 0.800, .022), (-0.115, 0.880, .020),
        (-0.020, 0.880, .020), (-0.430, 0.620, .022), (-0.300, 0.620, .022), (0.155, 0.635, .024), (0.275, 0.635, .022),
        (0.480, 0.810, .026), (0.480, 0.735, .026), (0.565, 0.775, .022)]
# name, x, z, w, h (screen opening), note: compact 2082 retrofit units (the round dials dominate the panel)
MFDS = [('mfd_center', -0.065, 0.615, 0.150, 0.110, 'retrofit tac unit in the lower centre stack (Cockpit.tacScreenRender)'),
        ('mfd_left', -0.555, 0.575, 0.120, 0.100, 'retrofit pilot tac unit, outboard lower left'),
        ('mfd_right', 0.540, 0.590, 0.120, 0.100, 'retrofit navigator tac unit, outboard lower right')]
# (the side units were drawn 0.105 x 0.078 / 0.110 x 0.082 in the panel art guide; they are 0.12 x 0.10 in the geometry: the
# contract's legibility floor. Their bezel blocks (0.147 x 0.137 m) cover the painted openings entirely.)
ANNUN = [(-0.065, 0.925), (0.30, 0.900)]          # small annunciator / warning-light clusters (art only)
RADIO = None
SWITCH_ROW_Z = 0.493
# lower switch panels under the main panel, either side of the pedestal (photo 44 / 47): x0, x1 (pilot side; mirrored)
LOWER_X = (0.115, 0.60)
LOWER_FRONT = (4.115, 0.335)                      # (y, z) of the aft/lower edge; the face rises to the panel bottom
LOWER_BACK = (4.205, 0.462)

GUIDE_W = 1700


def guide_size():
    x0, x1, z0, z1 = PANEL_RECT
    return GUIDE_W, int(GUIDE_W * (z1 - z0) / (x1 - x0))


def to_px(x, z):
    x0, x1, z0, z1 = PANEL_RECT
    W, H = guide_size()
    return (x - x0) / (x1 - x0) * W, (z1 - z) / (z1 - z0) * H


def draw_guides(path):
    from PIL import Image, ImageDraw
    x0, x1, z0, z1 = PANEL_RECT
    W, H = guide_size()
    sc = W / (x1 - x0)
    im = Image.new('RGB', (W, H), (255, 255, 255)); d = ImageDraw.Draw(im)
    pts = []
    for k in range(201):
        x = x0 + (x1 - x0) * k / 200
        pts.append(to_px(x, panel_top(x)))
    pts += [to_px(x1, z0 + 0.012), to_px(x1 - 0.012, z0), to_px(x0 + 0.012, z0), to_px(x0, z0 + 0.012)]
    d.polygon(pts, fill=(18, 18, 20))
    for _, x, z, r in REAL:
        u, v = to_px(x, z); rr = r * sc
        d.ellipse((u - rr - 8, v - rr - 8, u + rr + 8, v + rr + 8), fill=(70, 70, 72))
        d.ellipse((u - rr, v - rr, u + rr, v + rr), fill=(0, 0, 0))
    for x, z, r in DECO:
        u, v = to_px(x, z); rr = r * sc
        d.ellipse((u - rr - 6, v - rr - 6, u + rr + 6, v + rr + 6), fill=(70, 70, 72))
        d.ellipse((u - rr, v - rr, u + rr, v + rr), fill=(230, 230, 230))
    for _, x, z, w, h, _n in MFDS:
        a, b = to_px(x - w / 2, z + h / 2); c, e = to_px(x + w / 2, z - h / 2)
        d.rectangle((a - 10, b - 10, c + 10, e + 10), fill=(60, 60, 62)); d.rectangle((a, b, c, e), fill=(0, 0, 0))
    for x, z in ANNUN:
        for k in range(4):
            u, v = to_px(x - 0.03 + k * 0.02, z)
            d.ellipse((u - 7, v - 7, u + 7, v + 7), fill=(200, 60, 40) if k % 2 else (220, 160, 40))
    for k in range(20):
        x = -0.60 + k * 0.063
        if abs(x + 0.065) < 0.10:
            continue
        u, v = to_px(x, SWITCH_ROW_Z)
        d.rectangle((u - 6, v - 12, u + 6, v + 12), fill=(200, 200, 200))
    im.save(path)


# ---- the B-25H cockpit art atlas (b25h_ckart_b / _n, 4096^2): rect px (row 0 top), source file in
# assets/textures_v2/fal_raw_cockpit_b25h, crop or None
ATLAS = 4096
PANELS = {
    'panel':        ((0, 0, 4096, 1738), 'v3/panel_v3b_7322.png', None),
    'box_left':     ((0, 1746, 1360, 2652), 'box_left.png', None),
    'box_right':    ((1368, 1746, 2728, 2652), 'box_right.png', None),
    'pedestal':     ((2736, 1746, 4096, 2652), 'pedestal_face.png', None),
    'placards':     ((0, 2660, 1360, 3566), 'placards.png', None),
    'box_nav':      ((1368, 2660, 2728, 3566), 'box_nav.png', None),
    'bezel':        ((2736, 2660, 4096, 3426), 'retrofit_bezel.png', None),
    'lower_left':   ((0, 3574, 1600, 4090), 'v3/lower_left.png', (0.0, 0.11, 1.0, 0.86)),     # crop (u0, v0, u1, v1) of the source
    'lower_right':  ((1608, 3574, 3208, 4090), 'v3/lower_right.png', (0.0, 0.11, 1.0, 0.86)),
    'box_left2':    ((3216, 3434, 4096, 4090), 'v3/box_left2.png', None),
}
# measured fit of the v3 panel art (google/nano-banana-2.1/edit from panel_layout_guide_v3.png, seed 7322): source pixel
# u = PF_A * x + PF_B, v (row, down) = PF_C * z + PF_D over the 16 real-dial holes (mean residual 4.3 px, max 10.9 px);
# make_cockpit_art_b25h.measure() refits it every build and fails on > 4 px drift
PANEL_SRC_SIZE = (3168, 1344)
PF_A, PF_B, PF_C, PF_D = 2387.48, 1583.15, -2714.91, 2581.18


def uv(name, u, v):
    (x0, y0, x1, y1), _, _ = PANELS[name]
    x0, y0, x1, y1 = x0 + 2, y0 + 2, x1 - 2, y1 - 2
    return ((x0 + u * (x1 - x0)) / ATLAS, 1.0 - (y0 + (1.0 - v) * (y1 - y0)) / ATLAS)


def panel_uv(x, z):
    """atlas UV of a point (x, z) of the panel face, through the measured art fit (PF_*)."""
    W, H = PANEL_SRC_SIZE
    return uv('panel', (PF_A * x + PF_B) / W, 1.0 - (PF_C * z + PF_D) / H)


# measured landmarks of the fal art (textures/make_cockpit_art_b25h.py re-measures them every build, fails on > 4 px drift)
PED_SIZE = (1696, 2528)
PED_SLOT_U = [0.125, 0.2748, 0.4166, 0.5566, 0.6958, 0.8467]       # slot centres in the pedestal art (u)
PED_SLOT_X = [-0.072, -0.042, -0.014, 0.014, 0.042, 0.072]          # the geometry slots (x on the quadrant face)
PED_SLOT_V = (0.116, 0.839)                                          # slot ends in the art (v up) <-> -0.10 / +0.10 m on the face
PED_FACE = (0.20, 0.30)                                              # quadrant face width (x) and length (along the slope)
BEZEL_SIZE = (2752, 1536)
BEZEL_OPEN = (251 / 2752, 1 - 1210 / 1536, 2499 / 2752, 1 - 92 / 1536)   # u0, v0, u1, v1 of the black screen opening


def ped_u(x):
    """art u for face x (piecewise linear through the measured slot centres; edges -> 0 / 1)."""
    hx = PED_FACE[0] / 2
    kn = [(-hx, 0.0)] + list(zip(PED_SLOT_X, PED_SLOT_U)) + [(hx, 1.0)]
    for (x0, u0), (x1, u1) in zip(kn, kn[1:]):
        if x <= x1 + 1e-9:
            return u0 + (u1 - u0) * (x - x0) / (x1 - x0)
    return 1.0


def ped_v(t):
    """art v for a position t along the face slope (m, -0.15 .. +0.15, + = toward the panel)."""
    hl = PED_FACE[1] / 2
    kn = [(-hl, 0.0), (-0.10, PED_SLOT_V[0]), (0.10, PED_SLOT_V[1]), (hl, 1.0)]
    for (a, va), (b, vb) in zip(kn, kn[1:]):
        if t <= b + 1e-9:
            return va + (vb - va) * (t - a) / (b - a)
    return 1.0


if __name__ == '__main__':
    import sys
    draw_guides(sys.argv[1])
