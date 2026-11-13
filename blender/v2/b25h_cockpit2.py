"""B-25H cockpit, rebuilt as a historical B-25 cockpit (offline worker, 2026-11-01; pass 2 = v3 the same day).

The user rejected the old B-25H cockpit ("absolutely horrific" next to the GA-25X). Same method as the approved GA-25X 0.3.x:
reference study (refs\\b25_cockpit_user, local only), ALL art through fal (assets/fal_manifest.jsonl), hand modelling only for
structure / fit geometry, automatic checks, side-by-side with the photos.
  * art: fal panel / lower switch panels / boxes / pedestal / placards / retrofit bezel atlas (bk_art, b25h_cockpit_layout.py),
    quilted padding (bk_quilt) and olive-drab painted metal (bk_od) tiles;
  * 3D props: fal concept -> tripo image-to-3D -> tripo remesh (cockpit_kit.py): yoke wheel, column, throttle / prop / mixture
    levers, trim wheel, rudder pedals, seats; v3: column boot, navigator footrest, wiring looms. Each keeps its own baked
    texture (material pr_<name>);
  * historical H: ONE control column / wheel / pedal set (pilot, left); the right seat is the navigator / cannoneer station
    (no controls; footrest + boxes). FEATURES['copilot_controls'] = False.
Pass 2 (v3, the orchestrator's review of pass 1 against photos 44-49):
  * full-width main panel with an ARCHED top (layout panel_top) under a rounded black coaming shell lofted to the windshield
    base; no posts; compact retrofit screens; lower switch panels either side of the pedestal;
  * tall olive pedestal from the footwell floor to the panel bottom, quadrant on top, trim wheel on its left side;
  * footwells (FOOT_Z) for the crew figures' feet, pedals ahead of the pilot's toes, footrest for the navigator, heel plates,
    seat rails, column boot.
Contracts kept (B25HBuild.cs, contract_b25h_v2.py, B25H.Instruments Plugin.cs): cockpit_interior, cockpit_gauges, gauge_<id>
pivots + gauge_<id>_needle / _needle_short / _card movers (local +X toward the pilot, rest 12 o'clock), mfd_center / mfd_left /
mfd_right, quadrant_throttle_L/R (Cockpit.throttles), cockpit_column_L (pitch) / cockpit_yoke_L (roll) /
cockpit_rudder_pedals_L (yaw), cockpit_seat_L/R, crew_navigator_eye, gunsight_pilot / gunsight_combiner.
"""
import math
from mathutils import Vector, Quaternion, Matrix
import b25h_spec as S
from b25h_geom import V, MeshBuf, loft, fan_cap, annulus, oriented_quad, cylinder, box, circle_pts, ear_clip
from b25h_parts import Part
from b25h_v3 import frame_x, FLOOR_Z
import b25h_v3_cockpit as C3
import b25h_cockpit_layout as LY
import cockpit_kit as K
import b25h_dials184 as D184

PN, PU, RK = C3.PN, C3.PU, C3.RK
X_, Y_, Z_ = V((1, 0, 0)), V((0, 1, 0)), V((0, 0, 1))
CK = 'bk_od'                          # painted structure (olive drab tile)
HW = 0.66                             # cabin half width (quilt wall inner face)
Y0 = 2.66                             # aft cabin bulkhead
GAUGE_CELLS = {g[0]: (g[4], g[5]) for g in C3.GAUGES}      # id -> (face cell, movers) from the 1.1 table (atlas b25h_gauges)
GAUGE_CELLS.update({k: (GAUGE_CELLS[k][0], mv) for k, mv in D184.SMALL_MOVERS.items()})   # 1.8.4: the six small dials get needles
# ---- v3 cabin floor: seat deck at FLOOR_Z aft of STEP_Y, footwells at FOOT_Z ahead of it (crew figures' heels, COIN bone pose:
# heel ~-0.14 for eyes at z 1.10). The nose-wheel well top-front corner is chamfered (build_b25h_v2: WELL_CHAMFER) so the inner
# feet pass in front of it. The T13E1 breech under the pilot's footwell tops out at z -0.22 (y >= 4.12): the floor bottom is -0.19.
FOOT_Z = -0.170
FOOT_T = 0.020
STEP_Y = 3.83
WELL_CHAMFER = ((3.83, 0.06), (3.95, -0.22))     # (y, z) top-aft and front-low corners of the chamfer (fus_cockpit well box)
WELL_HX = S.NOSE_WELL_HALF_X - 0.01
FW_Y = 4.44                                      # footwell front wall (aft face), under the panel
PANEL_X = 0.70                                   # panel body / coaming half width (fus inner wall 0.705)
COAM_Y1 = 4.50                                   # coaming forward edge (under the windshield base frame)
# windshield base (measured from canopy_frame / canopy_glass / fus_nose: lowest z over y 4.45..4.55 per |x|) - 15 mm
WSB = [(0.0, 0.935), (0.2, 0.935), (0.3, 0.932), (0.4, 0.914), (0.5, 0.869), (0.55, 0.831), (0.6, 0.773), (0.65, 0.663), (0.70, 0.66)]


def wsb(x):
    x = abs(x)
    for (a, za), (b, zb) in zip(WSB, WSB[1:]):
        if x <= b:
            return za + (zb - za) * (x - a) / (b - a)
    return WSB[-1][1]


def art_quad(m, c, ux, uy, w, h, name, u0=0.0, v0=0.0, u1=1.0, v1=1.0):
    ux, uy = V(ux).normalized(), V(uy).normalized()
    n = ux.cross(uy)
    q = [c - ux * w / 2 - uy * h / 2, c + ux * w / 2 - uy * h / 2, c + ux * w / 2 + uy * h / 2, c - ux * w / 2 + uy * h / 2]
    uv = [LY.uv(name, u0, v0), LY.uv(name, u1, v0), LY.uv(name, u1, v1), LY.uv(name, u0, v1)]
    oriented_quad(m, q, 'bk_art', n, uv)


def basis(ux, uy):
    ux, uy = V(ux).normalized(), V(uy).normalized()
    n = ux.cross(uy).normalized()
    return Matrix((ux, uy, n)).transposed().to_quaternion()


def box_open(m, c, ux, uy, size, mat):
    """box without its front (+ux x uy) and back faces (the art quad covers the front, the back sits on a wall)."""
    ux, uy = V(ux).normalized(), V(uy).normalized()
    n = ux.cross(uy).normalized()
    w, h, d = (s_ / 2 for s_ in size)
    P = lambda a, b, cc: c + ux * (a * w) + uy * (b * h) + n * (cc * d)
    oriented_quad(m, [P(-1, -1, -1), P(1, -1, -1), P(1, -1, 1), P(-1, -1, 1)], mat, -uy)
    oriented_quad(m, [P(-1, 1, -1), P(1, 1, -1), P(1, 1, 1), P(-1, 1, 1)], mat, uy)
    oriented_quad(m, [P(-1, -1, -1), P(-1, 1, -1), P(-1, 1, 1), P(-1, -1, 1)], mat, -ux)
    oriented_quad(m, [P(1, -1, -1), P(1, 1, -1), P(1, 1, 1), P(1, -1, 1)], mat, ux)


def art_box(m, c, ux, uy, w, h, name, depth=0.06, proud=0.0, u0=0.0, v0=0.0, u1=1.0, v1=1.0):
    """switch / radio box: open box `depth` deep standing on a surface, its face = the art (proud of c by depth)."""
    ux, uy = V(ux).normalized(), V(uy).normalized()
    n = ux.cross(uy).normalized()
    box_open(m, c + n * (depth / 2 + proud), ux, uy, (w, h, depth), 'bk_black')
    art_quad(m, c + n * (depth + proud + 0.0005), ux, uy, w - 0.002, h - 0.002, name, u0, v0, u1, v1)


def fit_place(mb, name, R, sc, want, mat=None):
    """place prop `name` (world = anchor + R @ (p * sc)) so its world bbox meets `want`: dict axis -> ('min'|'max'|'mid', value)."""
    pts, _ = K.read_glb(K.glb_path(name))
    w = [R @ (p * sc) for p in pts]
    anc = V()
    for ax, (kind, val) in want.items():
        i = 'xyz'.index(ax)
        lo, hi = min(p[i] for p in w), max(p[i] for p in w)
        anc[i] = val - {'min': lo, 'max': hi, 'mid': (lo + hi) / 2}[kind]
    return K.place(mb, name, R, sc, V((0, 0, 0)), anc, mat=mat)


# ============================================================================================ cabin shell + floor
def cabin(m):
    """seat deck, footwells, quilted padding on the side walls, olive frames, sill, aft bulkhead."""
    T = 0.03
    # seat deck (FLOOR_Z) aft of STEP_Y, full width
    box(m, (0, (Y0 + STEP_Y) / 2, FLOOR_Z - T / 2), (2 * HW, STEP_Y - Y0, T), CK)
    # footwell floor (top FOOT_Z): outboard of the nose-wheel well from STEP_Y, over / ahead of it from the chamfer crossing
    (cy0, cz0), (cy1, cz1) = WELL_CHAMFER
    y_in = cy0 + (cy1 - cy0) * (cz0 - FOOT_Z) / (cz0 - cz1) + 0.006             # chamfer crosses the floor plane here
    for s in (-1, 1):
        box(m, (s * (WELL_HX + 0.003 + HW) / 2, (STEP_Y + FW_Y) / 2, FOOT_Z - FOOT_T / 2), (HW - WELL_HX - 0.003, FW_Y - STEP_Y, FOOT_T), CK)
        # riser: deck front edge down to the footwell (front 3 mm behind the deck end face, top 3 mm under the deck top)
        box(m, (s * (WELL_HX + 0.003 + HW) / 2, STEP_Y - 0.013, (FOOT_Z + FLOOR_Z - 0.003) / 2),
            (HW - WELL_HX - 0.003, 0.02, FLOOR_Z - 0.003 - FOOT_Z), CK)
        # well side wall facing the footwell (|x| = WELL_HX + 3 mm), between the riser and the chamfer
        box(m, (s * (WELL_HX + 0.013), (STEP_Y + cy1) / 2, (FOOT_Z + cz0) / 2), (0.02, cy1 - STEP_Y - 0.006, cz0 - FOOT_Z), CK)
    box(m, (0, (y_in + FW_Y) / 2, FOOT_Z - FOOT_T / 2), (2 * WELL_HX, FW_Y - y_in, FOOT_T), CK)
    # chamfer plate over the nose-wheel well's chamfered corner (3 mm proud of the fus well face)
    a_, b_ = V((0, cy0, cz0)), V((0, cy1, cz1))
    d_ = b_ - a_
    nq = V((0, -d_.z, d_.y)).normalized()
    if nq.z < 0:
        nq = -nq
    box(m, (a_ + b_) / 2 + nq * 0.006, (2 * WELL_HX - 0.012, d_.length - 0.004, 0.006), CK, rot=Quaternion(X_, math.atan2(d_.z, d_.y)))
    # footwell front wall under the panel (aft face at FW_Y), up to the lower switch panels' underside
    # v3: up to 0.50 (behind the panel body) so no gap under the panel shows the open nose structure / sky
    box(m, (0, FW_Y + 0.01, (FOOT_Z - FOOT_T + 0.50) / 2), (2 * HW, 0.02, 0.50 - FOOT_Z + FOOT_T), CK)
    for s in (-1, 1):
        # cap over the fuselage tear frame at y ~4.43-4.45 (fus_cockpit 'structure', its inboard flange showed in the footwell
        # corners in front of the front wall), wall to the outer pedal's side
        box(m, (s * (0.585 + HW - 0.001) / 2, (4.405 + FW_Y) / 2, (FOOT_Z + 0.002 + 0.50) / 2), (HW - 0.001 - 0.585, FW_Y - 4.405 - 0.002, 0.50 - FOOT_Z - 0.002), CK)
        # quilted padding blankets on the walls: upper (sill .. 0.44) to the panel, lower (footwell) to the front wall
        box(m, (s * (HW + 0.007), (Y0 + 4.20) / 2, 0.64), (0.01, 4.20 - Y0, 0.40), 'bk_quilt')    # inner face 2 mm off the fus frame at y 2.72
        box(m, (s * (HW + 0.007), (Y0 + FW_Y) / 2, (FOOT_Z - FOOT_T + 0.44) / 2 - 0.0015), (0.01, FW_Y - Y0, 0.44 - FOOT_Z + FOOT_T - 0.003), 'bk_quilt')
        for y in (2.95, 3.35, 3.75, 4.10):
            z0 = FOOT_Z if y > STEP_Y else FLOOR_Z
            box(m, (s * (HW - 0.012), y, (z0 + 0.84) / 2), (0.026, 0.035, 0.84 - z0), CK)
        box(m, (s * (HW - 0.010), (Y0 + 4.20) / 2, 0.85), (0.024, 4.20 - Y0, 0.03), CK)
    for rect in ((-1.0, -0.24, FLOOR_Z, 2.0), (0.24, 1.0, FLOOR_Z, 2.0), (-0.24, 0.24, 1.05, 2.0)):
        bulkhead(m, Y0, rect, 'bk_quilt')


def bulkhead(mb, y, rect, mat, inset=0.03, t=0.03):
    """aft bulkhead slab = fuselage inner section at y clipped to rect; v3: faces ear-clipped (b25h_interior.section_panel fans
    from the centroid, whose triangles overlap on the concave clipped outline: z-fight)."""
    from b25h_parts import fus_ring
    from b25h_interior import clip_poly
    poly = clip_poly([(p.x, p.z) for p in fus_ring(y, inset)], *rect)
    if len(poly) < 3:
        return
    clean = []
    for p in poly:
        if not clean or abs(p[0] - clean[-1][0]) + abs(p[1] - clean[-1][1]) > 1e-6:
            clean.append(p)
    if abs(clean[0][0] - clean[-1][0]) + abs(clean[0][1] - clean[-1][1]) <= 1e-6:
        clean.pop()
    cx = sum(p[0] for p in clean) / len(clean)
    cz = sum(p[1] for p in clean) / len(clean)
    area = sum(clean[k][0] * clean[(k + 1) % len(clean)][1] - clean[(k + 1) % len(clean)][0] * clean[k][1] for k in range(len(clean)))
    from mathutils.geometry import tessellate_polygon
    for yy, sgn in ((y + t / 2, 1), (y - t / 2, -1)):
        pts = [V((p[0], yy, p[1])) for p in clean]
        # triangulated (tessellate_polygon handles the concave clipped outline; no n-gons, no overlapping fan triangles),
        # shared vertices; winding: (x, z) counter-clockwise looks toward -y
        vid = [mb.v(p) for p in pts]
        for tri in tessellate_polygon([pts]):
            a_, b_, c_ = (pts[k] for k in tri)
            tri = list(tri)
            if ((b_ - a_).cross(c_ - a_)).y * sgn < 0:
                tri = [tri[0], tri[2], tri[1]]
            mb.face([vid[k] for k in tri], mat, None, False)
    for k in range(len(clean)):
        a, b = clean[k], clean[(k + 1) % len(clean)]
        q = [V((a[0], y - t / 2, a[1])), V((b[0], y - t / 2, b[1])), V((b[0], y + t / 2, b[1])), V((a[0], y + t / 2, a[1]))]
        oriented_quad(mb, q, mat, V(((a[0] + b[0]) / 2 - cx, 0, (a[1] + b[1]) / 2 - cz)))


def floor_details(m):
    """seat rails on the deck, anti-slip heel plates in the footwells."""
    for key in ('pilot', 'navigator'):
        sx, sy = S.CREW[key]['seat']
        for d in (-0.13, 0.13):
            box(m, (sx + d, sy + 0.05, FLOOR_Z + 0.006), (0.024, 0.62, 0.012), 'bk_black')
            for yy in (sy - 0.18, sy + 0.05, sy + 0.28):                       # rail lock holes / bolts
                cylinder(m, V((sx + d, yy, FLOOR_Z + 0.012)), V((sx + d, yy, FLOOR_Z + 0.016)), 0.007, N=8, mat='bk_od')
        eye = V(S.CREW[key]['eye'])
        r = eye + V((0, 0.0651, -0.7147))
        for side in (-1, 1):
            ax = r.x + side * 0.1722
            box(m, (ax, r.y + 0.5485 + 0.02, FOOT_Z + 0.003), (0.11, 0.24, 0.006), 'bk_black')


# ============================================================================================ instrument panel + coaming
def face_top(x):
    """top of the panel face (arch), inside the measured art outline."""
    return LY.panel_top(x)


def panel(m, gf):
    """black main panel with an arched top (fal art face over the art rect, cut to the arch), real dial bezels / faces."""
    x0, x1, z0, z1 = LY.PANEL_RECT
    # art face: vertical strips, each a quad cut to the arch (UVs through the measured art fit LY.panel_uv)
    NX = 52
    xs = [x0 + (x1 - x0) * i / NX for i in range(NX + 1)]
    for xa, xb in zip(xs, xs[1:]):
        ta, tb = face_top(xa), face_top(xb)
        NZ = 4
        for k in range(NZ):
            za0, za1 = z0 + (ta - z0) * k / NZ, z0 + (ta - z0) * (k + 1) / NZ
            zb0, zb1 = z0 + (tb - z0) * k / NZ, z0 + (tb - z0) * (k + 1) / NZ
            pts = [C3.panel_pt(xa, za0), C3.panel_pt(xb, zb0), C3.panel_pt(xb, zb1), C3.panel_pt(xa, za1)]
            uvs = [LY.panel_uv(xa, za0), LY.panel_uv(xb, zb0), LY.panel_uv(xb, zb1), LY.panel_uv(xa, za1)]
            oriented_quad(m, pts, 'bk_art', PN, uvs)
    # black side extensions of the face from the art edge to the walls (0.5 mm behind the art plane), body walls behind
    for s_ in (-1, 1):
        xa, xb = s_ * x1, s_ * PANEL_X
        n = 3
        for i in range(n):
            u0_, u1_ = xa + (xb - xa) * i / n, xa + (xb - xa) * (i + 1) / n
            pts = [C3.panel_pt(u0_, z0, -0.0005), C3.panel_pt(u1_, z0, -0.0005), C3.panel_pt(u1_, face_top(u1_), -0.0005),
                   C3.panel_pt(u0_, face_top(u0_), -0.0005)]
            oriented_quad(m, pts, 'bk_black', PN)
    # body: the outline extruded 6 cm back (side walls), bottom closure
    outline = [(x, face_top(x)) for x in [-PANEL_X + 2 * PANEL_X * i / 60 for i in range(61)]]
    for (xa, za), (xb, zb) in zip(outline, outline[1:]):
        a, b = C3.panel_pt(xa, za, -0.0008), C3.panel_pt(xb, zb, -0.0008)
        oriented_quad(m, [a, b, b - PN * 0.06, a - PN * 0.06], 'bk_black', PU)
    a, b = C3.panel_pt(-PANEL_X, z0, -0.0008), C3.panel_pt(PANEL_X, z0, -0.0008)
    oriented_quad(m, [a, b, b - PN * 0.06, a - PN * 0.06], 'bk_black', -PU)
    # real dials: bezel ring proud of the art, black backing, dial face (b25h_gauges cell) recessed; movers as in 1.1
    movers = []
    rt, up = X_, PU
    # 1.8.4: the REAL dials + real dials over the painted ones (b25h_dials184.OVER); every one has a needle / card mover
    dials = [(gid, gid, x, z, r) + GAUGE_CELLS[gid] for gid, x, z, r in LY.REAL]
    dials += [(gid, sid, x, z, r, D184.face_cell(sid), mv) for gid, sid, x, z, r, mv in D184.OVER]
    for gid, sid, x, z, r, cell, mv in dials:
        c = C3.panel_pt(x, z)
        ro = circle_pts(c + PN * 0.010, PN, r + 0.008, 24, ref=PU)
        ri = circle_pts(c + PN * 0.010, PN, r, 24, ref=PU)
        annulus(m, ro, ri, 'bk_black', PN)
        loft(m, [circle_pts(c + PN * 0.0005, PN, r + 0.008, 24, ref=PU), ro], 'bk_black')
        loft(m, [ri, circle_pts(c + PN * 0.002, PN, r, 24, ref=PU)], 'bk_black', outward=False)
        C3.disc_uv(gf, c, rt, up, r, cell, PN, 0.0055)
        if not mv:
            continue
        fr = frame_x(PN, PU)
        movers.append(Part(f'gauge_{gid}', 'cockpit_gauges', c, None, fr, info=dict(kind='gauge', face_cell=cell, radius=r)))
        for suf, kind, mcell in mv:
            nm = MeshBuf()
            if kind == 'card':
                # v3 FIX: the card was 0.5 mm BEHIND the dial face (0.005 vs 0.0055) since 1.1, so the attitude / heading cards were
                # hidden; now 1.3 mm in front of the face (under the needles' 7.5 mm)
                C3.disc_uv(nm, c, rt, up, r * 0.86, mcell, PN, 0.0068, N=32)
            else:
                # two-needle dials (altimeter): the long needle and its hub 2.5 mm higher (mesh only; the pivot stays), so the needles
                # and hub caps are >= 1 mm apart (they were 0.5 mm: z-fight)
                two = sum(1 for m_ in mv if m_[1] != 'card') > 1
                C3.needle_mesh(nm, c + (PN * 0.0025 if (two and kind == 'needle') else V()), rt, up, r, kind, mcell)
            key = gid if suf in ('needle', 'card') else gid + '_short'
            sc = C3.GAUGE_SCALE.get(key, {}) or D184.info_for(sid)
            info = dict(kind='gauge_' + kind, axis_local='+X (Unity) = toward the pilot', rest="12 o'clock (local +Y Unity = panel up)",
                        cell=mcell, sign='Unity +angle about local +X = clockwise as seen by the pilot', **sc)
            if 'sweep' in sc:
                info['deg_per_unit'] = round(sc['sweep'] / (sc['v1'] - sc['v0']), 6)
            part = Part(f'gauge_{gid}_{suf}', f'gauge_{gid}', c, nm, fr, info=info)
            part.own_uv = True
            movers.append(part)
    # retrofit screens: compact units; bezel art frame (opening cut out) on a black block, screen face recessed 4 mm
    mfd_parts = []
    bu0, bv0, bu1, bv1 = LY.BEZEL_OPEN
    for nmn, x, z, w, h, note in LY.MFDS:
        c = C3.panel_pt(x, z)
        W_, H_ = w / (bu1 - bu0), h / (bv1 - bv0)
        front = c + PN * 0.014
        ox0, oy0 = -W_ / 2 + bu0 * W_, -H_ / 2 + bv0 * H_
        for (cx, cy, sw, sh) in ((0, (oy0 + h + H_ / 2) / 2, W_, H_ / 2 - (oy0 + h)), (0, (-H_ / 2 + oy0) / 2, W_, oy0 + H_ / 2),
                                 ((-W_ / 2 + ox0) / 2, oy0 + h / 2, ox0 + W_ / 2, h), ((ox0 + w + W_ / 2) / 2, oy0 + h / 2, W_ / 2 - (ox0 + w), h)):
            box_open(m, front + rt * cx + up * cy - PN * 0.0065, rt, up, (sw, sh, 0.013), 'bk_black')

        def aq(xa, ya, xb, yb):
            art_quad(m, front + PN * 0.0005 + rt * ((xa + xb) / 2) + up * ((ya + yb) / 2), rt, up, xb - xa, yb - ya, 'bezel',
                     (xa + W_ / 2) / W_, (ya + H_ / 2) / H_, (xb + W_ / 2) / W_, (yb + H_ / 2) / H_)
        aq(-W_ / 2, oy0 + h, W_ / 2, H_ / 2); aq(-W_ / 2, -H_ / 2, W_ / 2, oy0)
        aq(-W_ / 2, oy0, ox0, oy0 + h); aq(ox0 + w, oy0, W_ / 2, oy0 + h)
        sm = MeshBuf()
        cs = front - PN * 0.004 + rt * (ox0 + w / 2) + up * (oy0 + h / 2)
        pts = [cs - rt * (w / 2) - up * (h / 2), cs + rt * (w / 2) - up * (h / 2), cs + rt * (w / 2) + up * (h / 2), cs - rt * (w / 2) + up * (h / 2)]
        oriented_quad(sm, pts, 'screen', PN, [(0, 0), (1, 0), (1, 1), (0, 1)])
        bk = front - PN * 0.011                            # backing inside the bezel block, 3 mm in front of the panel art
        oriented_quad(m, [bk - rt * (w / 2 + 0.004) - up * (h / 2 + 0.004), bk + rt * (w / 2 + 0.004) - up * (h / 2 + 0.004),
                          bk + rt * (w / 2 + 0.004) + up * (h / 2 + 0.004), bk - rt * (w / 2 + 0.004) + up * (h / 2 + 0.004)], 'screen', PN)
        mp = Part(nmn, 'fus_cockpit', cs, sm, info=dict(kind='mfd', size_m=(w, h), normal_unity=(0.0, round(PN.z, 4), round(PN.y, 4)),
                                                         uv='0-1; u -> pilot right, v -> panel up', note=note + ' (2082 retrofit unit, fal bezel art)'))
        mp.own_uv = True
        mfd_parts.append(mp)
    return movers + mfd_parts


def coaming_profile(x):
    """(y, z) points of the coaming shell section at x: from the panel's top edge, under and round the padded lip toward the
    crew, over the crest, forward and down to the windshield base."""
    zt = face_top(min(abs(x), PANEL_X))
    A = C3.panel_pt(x, zt)
    P = lambda v: (v.y, v.z)
    pts = [P(A - PN * 0.004 - PU * 0.004)]
    for ang in range(-90, 91, 30):                         # rounded lip, radius 18 mm, its centre 40 mm in front of the face
        a = math.radians(ang)
        c = A + PN * 0.040 + PU * 0.018
        pts.append(P(c + PN * (0.018 * math.cos(a)) + PU * (0.018 * math.sin(a))))
    yc, zc = pts[-1]
    zf = wsb(x)
    crest = (A.y + 0.03, zt + 0.042)
    pts += [(yc - 0.010, zc + 0.002), crest, (A.y + 0.12, min(zt + 0.035, zf + 0.025)), (COAM_Y1 - 0.06, zf + 0.008), (COAM_Y1, zf)]
    return pts


def coaming(m):
    """rounded black coaming / glareshield shell over the whole panel width, blending into the walls (no posts)."""
    NXS = 36
    xs = [-PANEL_X + 2 * PANEL_X * i / NXS for i in range(NXS + 1)]
    prof = [coaming_profile(x) for x in xs]
    for i in range(NXS):
        for j in range(len(prof[0]) - 1):
            (ya, za), (yb, zb) = prof[i][j], prof[i][j + 1]
            ty, tz = yb - ya, zb - za
            nrm = V((0, -tz, ty))                           # (y, z) normal: down under the lip, up on the top
            q = [V((xs[i], ya, za)), V((xs[i + 1], prof[i + 1][j][0], prof[i + 1][j][1])),
                 V((xs[i + 1], prof[i + 1][j + 1][0], prof[i + 1][j + 1][1])), V((xs[i], yb, zb))]
            oriented_quad(m, q, 'bk_black', nrm)
    for i, s in ((0, -1), (NXS, 1)):                       # end caps against the walls
        pr = prof[i]
        for a, b, c in ear_clip(pr):                       # ear-clipped (the lip makes the section concave)
            oriented_quad(m, [V((xs[i], pr[k][0], pr[k][1])) for k in (a, b, c)], 'bk_black', V((s, 0, 0)))


def coaming_z(x, y):
    """height of the coaming top at (x, y) (for parts standing on it)."""
    pr = coaming_profile(x)
    k = pr.index(max(pr, key=lambda p: p[1]))
    top = pr[k:]
    for (ya, za), (yb, zb) in zip(top, top[1:]):
        if ya <= y <= yb:
            return za + (zb - za) * (y - ya) / (yb - ya)
    return top[0][1]


def lower_panels(m):
    """lower switch panels under the main panel either side of the pedestal (fal art), on boxes closing down to the footwell."""
    (yf, zf), (yb, zb) = LY.LOWER_FRONT, LY.LOWER_BACK
    xa, xb = LY.LOWER_X
    for s, name in ((-1, 'lower_left'), (1, 'lower_right')):
        cx = s * (xa + xb) / 2
        w = xb - xa
        a, b = V((0, yf, zf)), V((0, yb, zb))
        uy = (b - a).normalized()
        c = V((cx, (yf + yb) / 2, (zf + zb) / 2))
        # face (art) 4 mm proud of the support box top; the box fills down to the panel body
        nrm = X_.cross(uy)                                 # (0, -dz, dy): toward the crew and up
        art_quad(m, c + nrm * 0.0045, X_, uy, w, (b - a).length, name)
        box(m, c + nrm * 0.001, (w, (b - a).length, 0.002), 'bk_black', rot=Quaternion(X_, math.atan2(uy.z, uy.y)))   # backing plate 2.5 mm under the art
        # support: front skirt (vertical, from the face front edge down 2 cm), sides, underside to the footwell front wall
        box(m, (cx, yf + 0.01, zf - 0.008), (w + 0.006, 0.02, 0.024), 'bk_black')
        box(m, (cx, (yf + FW_Y) / 2 + 0.01, zf - 0.022), (w + 0.006, FW_Y - yf, 0.006), 'bk_black')
        # outboard closure between the lower panel's end and the wall, under the main panel
        xo0, xo1 = xb + 0.0115, HW - 0.004                  # starts 1 mm outboard of the side box
        box(m, (s * (xo0 + xo1) / 2, (yf + FW_Y) / 2 + 0.004, (zf - 0.02 + zb) / 2),
            (xo1 - xo0, FW_Y - yf - 0.016, zb + 0.02 - zf), 'bk_black')
        for e in (-1, 1):
            xe = cx + e * (w / 2 + 0.006)
            box(m, (xe, (yf + yb) / 2 + 0.0115, (zf + zb) / 2 - 0.0085), (0.008, yb - yf + 0.017, zb - zf + 0.017), 'bk_black')   # 3 mm off the skirt faces


# ============================================================================================ pedestal + levers
QUAD_Y, QUAD_TOP = 4.040, 0.500       # v3: tall pedestal, quadrant face centre (y, z)
QUAD_TILT = C3.QUAD_TILT
THROTTLE_REST, THROTTLE_RANGE = C3.THROTTLE_REST, C3.THROTTLE_RANGE
LEVER_LEN = 0.135
PED_HX = 0.085                        # pedestal body half width (the quadrant housing is LY.PED_FACE wide)


def qpt(x, dy):
    """point on the sloped quadrant face, dy along the slope from its centre (+ = toward the panel)."""
    return V((x, QUAD_Y + dy * math.cos(QUAD_TILT), QUAD_TOP + dy * math.sin(QUAD_TILT)))


def lever_R(tilt_deg):
    """model -> world for the levers: model X -> world forward, model Y -> world -X (right-handed), model Z = lever axis,
    then tilted about world X by the face tilt + tilt_deg (positive = top aft)."""
    M0 = K.basis(Y_, -X_, Z_)
    return Matrix.Rotation(QUAD_TILT + math.radians(tilt_deg), 3, 'X') @ M0


SLOT_W = {0: 0.0085, 1: 0.0085, 2: 0.0115, 3: 0.0115, 4: 0.0085, 5: 0.0085}    # slot half widths (throttle slots wider: blade + hub)
SLOT_D = 0.075                                                             # slot well depth under the face


def stalk_mid(name, z0=0.06, z1=0.30):
    """model (x, y) centre of a lever's stalk (points between z0 and z1 of its height): the generated grips are off-centre."""
    pts, _ = K.read_glb(K.glb_path(name))
    lo, hi = K.bbox(pts)
    sel = [p for p in pts if lo.z + z0 * (hi.z - lo.z) <= p.z <= lo.z + z1 * (hi.z - lo.z)]
    a, b = K.bbox(sel)
    return (a.x + b.x) / 2, (a.y + b.y) / 2


def pedestal(m, parts):
    q = Quaternion(V((1, 0, 0)), QUAD_TILT)
    up = q @ Z_
    fw, fl = LY.PED_FACE
    # tall body from the footwell floor up under the quadrant housing, back part up to the panel bottom
    yb0, yb1 = qpt(0, -fl / 2).y + 0.012, C3.panel_pt(0, LY.PANEL_RECT[2]).y - 0.004
    zb1 = qpt(0, -fl / 2).z - 0.075
    box(m, (0, (yb0 + yb1) / 2, (FOOT_Z + 0.004 + zb1) / 2), (2 * PED_HX, yb1 - yb0, zb1 - FOOT_Z - 0.004), 'bk_od')
    box(m, (0, (qpt(0, fl / 2).y + yb1) / 2 + 0.002, (zb1 + LY.PANEL_RECT[2] + 0.004) / 2),
        (2 * PED_HX, yb1 - qpt(0, fl / 2).y - 0.004, LY.PANEL_RECT[2] + 0.004 - zb1), 'bk_od')
    box(m, (0, (yb0 + yb1) / 2, FOOT_Z + 0.0215), (2 * PED_HX + 0.03, yb1 - yb0 + 0.03, 0.039), 'bk_black')     # foot flange (2 mm off the floor)
    hc = qpt(0, 0) - up * 0.04
    box_open(m, hc, X_, q @ Y_, (fw, fl, 0.08), 'bk_od')                                                    # housing sides
    box(m, qpt(0, 0) - up * 0.081, (fw - 0.006, fl - 0.006, 0.004), 'bk_od', rot=q)                  # housing bottom
    # face: quads split at the slot positions, UVs through the measured slot landmarks (ped_u / ped_v)
    xs = [-fw / 2] + [x + d for k, x in enumerate(LY.PED_SLOT_X) for d in (-SLOT_W[k], SLOT_W[k])] + [fw / 2]
    ts = [-fl / 2, -0.10, 0.10, fl / 2]
    for i in range(len(xs) - 1):
        for k in range(len(ts) - 1):
            xa, xb, ta, tb = xs[i], xs[i + 1], ts[k], ts[k + 1]
            if (i % 2 == 1) and k == 1:
                continue                                   # slot opening: no face, a dark slot well below
            pts = [qpt(xa, ta), qpt(xb, ta), qpt(xb, tb), qpt(xa, tb)]
            uvs = [LY.uv('pedestal', LY.ped_u(xa), LY.ped_v(ta)), LY.uv('pedestal', LY.ped_u(xb), LY.ped_v(ta)),
                   LY.uv('pedestal', LY.ped_u(xb), LY.ped_v(tb)), LY.uv('pedestal', LY.ped_u(xa), LY.ped_v(tb))]
            oriented_quad(m, pts, 'bk_art', up, uvs)
    for k, x in enumerate(LY.PED_SLOT_X):                                                                  # slot wells
        sw = SLOT_W[k]
        for s in (-1, 1):
            a, b = qpt(x + s * sw, -0.10), qpt(x + s * sw, 0.10)
            oriented_quad(m, [a, b, b - up * SLOT_D, a - up * SLOT_D], 'bk_black', V((-s, 0, 0)))
        a, b = qpt(x - sw, -0.10) - up * SLOT_D, qpt(x + sw, 0.10) - up * SLOT_D
        oriented_quad(m, [a, V((b.x, a.y, a.z)), b, V((a.x, b.y, b.z))], 'bk_black', up)
        for t_, sg in ((-0.10, 1), (0.10, -1)):
            a = qpt(x - sw, t_); b = qpt(x + sw, t_)
            oriented_quad(m, [a, b, b - up * SLOT_D, a - up * SLOT_D], 'bk_black', (q @ Y_) * sg)
    # static levers (fal props): prop pitch (black knobs) inboard pair, mixture (red knobs) outer pair, at mid travel
    for name, xs_ in (('proplever', (-0.042, 0.042)), ('mixture', (-0.072, 0.072))):
        lo, hi = K.model_bbox(name)
        sc = LEVER_LEN / (hi.z - lo.z)
        for x in xs_:
            piv = qpt(x, 0.0) - up * 0.018
            mx, my = stalk_mid(name, 0.15, 0.45)
            K.place(m, name, lever_R(-4.0), sc, V((mx, my, lo.z + 0.06 * (hi.z - lo.z))), piv)
    # trim wheel on the pedestal's left side (face -X), below the housing
    lo, hi = K.model_bbox('trimwheel')
    sc = 0.20 / max(hi.y - lo.y, hi.z - lo.z)
    K.place(m, 'trimwheel', K.basis(-X_, -Y_, Z_), sc, V((lo.x, (lo.y + hi.y) / 2, (lo.z + hi.z) / 2)), V((-PED_HX - 0.002, 4.10, 0.27)))
    # aft face of the pedestal: a lower switch box and the fuel-selector / gear placards (crops of existing fal art)
    yf = yb0
    art_box(m, V((0, yf, 0.27)), X_, Z_, 0.15, 0.11, 'box_left', depth=0.025, u0=0.52, v0=0.0, u1=1.0, v1=0.42)
    art_box(m, V((-0.035, yf, 0.13)), X_, Z_, 0.075, 0.045, 'placards', depth=0.003, u0=0.04, v0=0.06, u1=0.36, v1=0.24)
    art_box(m, V((0.040, yf, 0.13)), X_, Z_, 0.060, 0.042, 'placards', depth=0.003, u0=0.38, v0=0.06, u1=0.62, v1=0.24)
    # throttles (animated): fal throttle lever per engine; object pivot = lever hub, local X = lateral (Cockpit.throttles)
    lo, hi = K.model_bbox('throttle')
    sc = LEVER_LEN / (hi.z - lo.z)
    for L, x in (('L', -0.014), ('R', 0.014)):
        piv = qpt(x, 0.0) - up * THR_HUB_DEPTH
        lm = MeshBuf()
        M0 = K.basis(-Y_, X_, Z_)                                      # grip bar across (model Y -> world X)
        # v3: the generated T-grip is 6.8 cm wide and crossed the neighbouring prop levers: lateral scale 0.45 (grip ~3 cm,
        # stalk ~8 mm in its 23 mm slot), a B-25 style narrow throttle knob pair
        R = Matrix.Rotation(QUAD_TILT + math.radians(THROTTLE_REST), 3, 'X') @ M0 @ Matrix.Diagonal((1.0, 0.45, 1.0))
        az = lo.z + 0.06 * (hi.z - lo.z)
        mx, my = stalk_mid('throttle', 0.25, 0.45)
        # the generated hub is wider than the slot: the lever is cut 8 mm under the face (the hidden hub stays out)
        K.place(lm, 'throttle', R, sc * THR_SCALE, V((mx, my, az)), piv, mat='pr_throttle',
                clip=(2, az + (THR_HUB_DEPTH - 0.008) / (sc * THR_SCALE)))
        parts.append(Part(f'quadrant_throttle_{L}', 'fus_cockpit', piv, lm, Quaternion(),
                          info=dict(kind='throttle_lever', axis_local='+X (Unity) = right (lateral)', rest_deg=THROTTLE_REST,
                                    range_deg=THROTTLE_RANGE, drive='Cockpit.throttles[] rotation',
                                    sign='Unity +angle about local +X moves the lever top FORWARD (as the column); idle at rest',
                                    note='fal-generated throttle lever (tripo3d image-to-3D + remesh) in its slot')))


THR_HUB_DEPTH = 0.030                 # throttle hub this far under the face (inside the deeper, wider slot well)
THR_SCALE = 1.0 + 0.012 / LEVER_LEN   # lever lengthened by the extra hub depth so the grip height stays
THR_CLIP = None


# ============================================================================================ stations
def seat(key, L, parts):
    sx, sy = S.CREW[key]['seat']
    lo, hi = K.model_bbox('seat')
    sm = MeshBuf()
    sc = 1.0 / (hi.z - lo.z)                              # 1.0 m tall bucket seat with armour back
    K.place(sm, 'seat', K.basis(Y_, -X_, Z_), sc, V(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z)), V((sx, sy - 0.06, FLOOR_Z + 0.012)))
    parts.append(Part(f'cockpit_seat_{L}', 'fus_cockpit', (sx, sy, FLOOR_Z), sm, info=dict(kind='crew_seat', crew=key,
                                                                                           note='fal-generated WWII bucket seat (tripo)')))


YOKE_FWD = 0.05
COL_Y = 3.985                         # column base / hub y
HUB_Z = 0.700                         # wheel hub height: under the pilot's sight line to the lower flight dials (0.80 at y 3.98)
PEDAL_Y = 4.300                       # pedal plates' aft-most point, ahead of the pilot's toes (toe tip y 4.31 at z -0.02)
PEDAL_H, PEDAL_UPRIGHT = 0.150, 10.0  # pedal height; extra tilt (deg) of the prop toward upright (plate normal (0, -0.94, 0.34))
PLATE_TOP = FOOT_Z + 0.008


def controls(m, parts):
    """pilot only (historical H): column (pitch) + yoke wheel (roll) + rudder pedals (yaw)."""
    sx, sy = S.CREW['pilot']['seat']
    # ---- column (fal): base on the footwell floor plate; model +Y (the hub flange side) -> world -Y (toward the pilot)
    lo, hi = K.model_bbox('column')
    R = K.basis(-X_, -Y_, Z_)
    base_m = V(((lo.x + hi.x) / 2 + 0.045, (lo.y + hi.y) / 2 - 0.04, lo.z))
    top_m = V((-0.08, 0.10, hi.z - 0.04))                 # the hub flange (measured from the model: top region y up to 0.109)
    sc = (HUB_Z - PLATE_TOP) / (top_m.z - base_m.z)
    # v3: the generated column leans 7 deg sideways; a shear about its base makes the shaft vertical, base and hub on the pilot's
    # axis (pass 1 shifted the base outboard instead: it stood in the pilot's left shin)
    kx = -(top_m.x - base_m.x) / (top_m.z - base_m.z)
    R = R @ Matrix(((1, 0, kx), (0, 1, 0), (0, 0, 1)))
    base_w = V((sx, COL_Y, PLATE_TOP))
    cm = MeshBuf()
    K.place(cm, 'column', R, sc, base_m, base_w)
    hub = base_w + R @ ((top_m - base_m) * sc)
    piv = V((base_w.x, COL_Y, FOOT_Z + 0.045))
    parts.append(Part('cockpit_column_L', 'fus_cockpit', piv, cm, Quaternion(),
                      info=dict(kind='control_column', axis_local='+X (Unity) = right (lateral)', range_deg=12,
                                drive='ControlSurface.pitchRange (or Cockpit.Joystick: its X term)',
                                sign='Unity +angle about local +X moves the column top FORWARD (push); pull = negative',
                                note='fal-generated B-25 control column (tripo)')))
    box(m, (base_w.x, COL_Y, FOOT_Z + 0.005), (0.20, 0.18, 0.006), 'bk_black')              # floor plate under the column base
    # column boot (fal): the pleated dust boot round the column base, on the floor plate
    lo, hi = K.model_bbox('boot')
    fit_place(m, 'boot', Matrix.Identity(3), 0.16 / max(hi.x - lo.x, hi.y - lo.y),
              dict(x=('mid', base_w.x), y=('mid', COL_Y), z=('min', PLATE_TOP + 0.001)))
    # ---- yoke wheel (fal): wheel face (model +X) toward the pilot along the hub axis a; width along world X
    a = V((0, -1, 0.30)).normalized()
    lo, hi = K.model_bbox('yoke')
    ysc = 0.36 / (hi.y - lo.y)
    R = K.basis(a, X_, a.cross(X_))                       # right-handed: model Z -> a x X (up, tilted with the hub)
    ym = MeshBuf()
    hub_m = V((-0.12 + YOKE_FWD / ysc, 0.0, -0.03))        # v3: shaft 5 cm further into the hub: wheel 0.33-0.51 m ahead of the eye
    K.place(ym, 'yoke', R, ysc, hub_m, hub)
    parts.append(Part('cockpit_yoke_L', 'cockpit_column_L', hub, ym, frame_x(a, (0, 0, 1)),
                      info=dict(kind='control_wheel', axis_local='+X (Unity) = hub axis, toward the pilot', range_deg=45,
                                drive='ControlSurface.rollRange', sign='Unity +angle about local +X turns the wheel top to the RIGHT (= right roll)',
                                note='fal-generated ram\'s-horn wheel (tripo)')))
    # ---- rudder pedals: yaw bar on a footwell-floor post (structure) + two fal pedals ahead of the toes; local X = up
    pp = V((sx, PEDAL_Y + 0.085, FOOT_Z))
    pm = MeshBuf()
    cylinder(pm, pp + V((0, 0, 0.012)), pp + V((0, 0, 0.07)), 0.022, N=12, mat='bk_black')
    bar_z = FOOT_Z + 0.05
    cylinder(pm, V((sx - 0.19, pp.y, bar_z)), V((sx + 0.19, pp.y, bar_z)), 0.015, N=8, mat='bk_black')
    lo, hi = K.model_bbox('pedal')
    psc = PEDAL_H / (hi.z - lo.z)
    Rp = Matrix.Rotation(math.radians(PEDAL_UPRIGHT), 3, 'X') @ K.basis(-Y_, X_, Z_)    # plate 70 deg: toes clear, foot presses fwd
    for k in (-1, 1):
        fit_place(pm, 'pedal', Rp, psc, dict(x=('mid', sx + k * 0.172), y=('min', PEDAL_Y), z=('min', FOOT_Z + 0.004)))
    cylinder(m, pp - V((0, 0, 0.0)), pp + V((0, 0, 0.012)), 0.036, N=12, mat='bk_black')
    parts.append(Part('cockpit_rudder_pedals_L', 'fus_cockpit', pp, pm, frame_x((0, 0, 1), (0, 1, 0)),
                      info=dict(kind='rudder_pedals', axis_local='+X (Unity) = up', range_deg=15, drive='ControlSurface.yawRange',
                                sign='Unity +angle about local +X (up) moves the RIGHT pedal AFT; right rudder = negative',
                                note='fal-generated pedals (tripo) on the yaw bar, ahead of the pilot\'s toes in the footwell')))
    # ---- navigator footrest (fal) ahead of his toes
    nx = S.CREW['navigator']['seat'][0]
    lo, hi = K.model_bbox('footrest')
    Rf = Matrix.Diagonal((0.38 / (hi.x - lo.x), 0.18 / (hi.y - lo.y), 0.072 / (hi.z - lo.z)))   # low ribbed platform under the balls of the feet
    fit_place(m, 'footrest', Rf, 1.0, dict(x=('mid', nx), y=('mid', FOOTREST_Y), z=('min', FOOT_Z + 0.001)))


FOOTREST_Y = 4.25                     # navigator's feet rest on it (sole at the ball ~ -0.08, platform top -0.097)


def side_equipment(m):
    """switch / radio boxes, wiring looms and placards on the walls (pilot left: electrical + equipment boxes;
    navigator right: radio controller + gun/bomb panel)."""
    # left wall, beside the pilot's knee: electrical switch box (art faces inboard)
    art_box(m, V((-HW - 0.001, 3.98, 0.64)), Y_, Z_, 0.28, 0.19, 'box_left', depth=0.06)
    # left wall abeam the seat: oxygen / interphone / breaker equipment box (v3)
    art_box(m, V((-HW - 0.001, 3.56, 0.66)), Y_, Z_, 0.24, 0.18, 'box_left2', depth=0.05)
    # right wall: SCR-274 style radio controller, and the navigator / cannoneer gun-and-bomb panel forward of it
    art_box(m, V((HW + 0.001, 3.30, 0.66)), -Y_, Z_, 0.28, 0.19, 'box_right', depth=0.07)
    art_box(m, V((HW + 0.001, 3.98, 0.64)), -Y_, Z_, 0.28, 0.19, 'box_nav', depth=0.06)
    # wiring looms (fal) along both walls above the boxes, and down to the left boxes
    lo, hi = K.model_bbox('loom')                         # model +Y = the loom's length
    for s, (ya, yb) in ((-1, (2.80, 3.40)), (-1, (3.44, 4.14)), (1, (2.80, 3.14)), (1, (3.48, 4.14))):
        L_ = yb - ya
        R = Matrix.Diagonal((0.45, 1.0, 0.5))             # slimmer bundle: ~2-3 cm thick
        fit_place(m, 'loom', R, L_ / (hi.y - lo.y), dict(x=('max', s * (HW - 0.024)) if s > 0 else ('min', -(HW - 0.024)), y=('min', ya), z=('mid', 0.80)))
        # standoff brackets from the quilt to the loom at its three clamps (the welded / decimated loom showed it hung 1.5-2.5 cm
        # off the wall with nothing holding it)
        for f in (0.17, 0.5, 0.83):
            box(m, (s * (HW - 0.012), ya + f * L_, 0.80), (0.022, 0.016, 0.014), CK)
    # placards (fal placards sheet crops): real size, next to the boxes and on the aft bulkhead
    art_box(m, V((-HW - 0.001, 3.56, 0.545)), Y_, Z_, 0.07, 0.035, 'placards', depth=0.003, u0=0.0, v0=0.62, u1=0.34, v1=1.0)
    art_box(m, V((-HW - 0.001, 3.20, 0.62)), Y_, Z_, 0.06, 0.04, 'placards', depth=0.003, u0=0.66, v0=0.62, u1=1.0, v1=1.0)
    art_box(m, V((HW + 0.001, 3.62, 0.66)), -Y_, Z_, 0.075, 0.05, 'placards', depth=0.003, u0=0.0, v0=0.20, u1=0.34, v1=0.58)
    art_quad(m, V((-0.30, Y0 + 0.0175, 0.85)), X_, Z_, 0.10, 0.065, 'placards', 0.0, 0.62, 0.34, 1.0)
    art_quad(m, V((0.30, Y0 + 0.0175, 0.85)), X_, Z_, 0.10, 0.065, 'placards', 0.66, 0.62, 1.0, 1.0)


# ============================================================================================ build
def build_cockpit():
    parts = []
    m = MeshBuf()
    gf = MeshBuf()
    cabin(m)
    floor_details(m)
    parts += panel(m, gf)
    coaming(m)
    lower_panels(m)
    pedestal(m, parts)
    side_equipment(m)
    controls(m, parts)
    for key, L in (('pilot', 'L'), ('navigator', 'R')):
        seat(key, L, parts)
    parts.append(Part('crew_navigator_eye', 'fus_cockpit', S.CREW['navigator']['eye'], None,
                      info=dict(kind='crew_eye', crew='navigator', look='+Z (Unity) forward')))
    # gunsight (N-3B style reflector, kept) standing on the coaming top above the pilot's panel
    gs = MeshBuf()
    gx = S.COCKPIT_EYE[0]
    gy = 4.30
    zt = coaming_z(gx, gy) - 0.004
    box(gs, (gx, gy, zt + 0.03), (0.07, 0.12, 0.06), 'bk_black')
    box(gs, (gx, gy - 0.055, zt + 0.07), (0.05, 0.05, 0.02), 'bk_black')
    cmb = MeshBuf()
    cq = Quaternion(V((1, 0, 0)), math.radians(-35))
    cc = V((gx, gy - 0.07, zt + 0.107))
    cpts = [cc + cq @ V(p) for p in ((-0.035, 0, -0.027), (0.035, 0, -0.027), (0.035, 0, 0.027), (-0.035, 0, 0.027))]
    oriented_quad(cmb, cpts, 'glass', V((0, -1, 0.3)))
    oriented_quad(cmb, cpts, 'glass', V((0, 1, -0.3)))
    parts.insert(0, Part('cockpit_interior', 'fus_cockpit', (0, 3.45, FLOOR_Z), m,
                         info=dict(note='B-25H cockpit rebuild (2026-11-01, v3): fal art + fal 3D props; historical H layout')))
    g = Part('cockpit_gauges', 'fus_cockpit', (0, S.PANEL_Y, 0.70), gf, info=dict(note='real dial faces (8x8 b25h_gauges atlas)'))
    g.own_uv = True
    parts.append(g)
    parts.append(Part('gunsight_pilot', 'fus_cockpit', (gx, gy, zt), gs, info=dict(note='N-3B style reflector sight')))
    parts.append(Part('gunsight_combiner', 'gunsight_pilot', cc, cmb, info=dict(kind='combiner', note='glass quad; reticle material slot')))
    return parts
