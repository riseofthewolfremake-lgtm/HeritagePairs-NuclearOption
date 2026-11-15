r"""Heritage Pairs 1.9.12: GA-25X airbrake panels (two SHOULDER panels on fus_rear), built as an ADD-ON to the shipped model.

Why an add-on FBX and not a change in build_ga25x.py (measured 2026-11-14, study1912ga25x_airbrake
egen_base): a rebuild of the
GA-25X from today's generator sources does NOT reproduce the shipped 1.9.11 model (the shared B-25H builders moved on after the model was
last built on 11-08: fus_forward 444 -> 944 atlas points, 96,763 -> 97,905 triangles) and the atlas pack moves all 62 paint parts. So the
main model (ga25x.blend / ga25x.fbx) is only READ here and stays byte-identical; the panels go into their own small FBX
(ga25x_airbrake.fbx, the ga25x_propdisc.fbx pattern) that GA25XBuild.cs adds under fus_rear when AirbrakePanels1912 is true.

Round 2 (review of the first build): the first site was the flank, where every livery carries its faction mark, so the mark swung out
with the panel. The panels now sit on the upper SHOULDERS of the rear fuselage (the stock FS-12 layout: one curved panel each side of the
upper fuselage, hinge line tilted; the stock T/A-30 panel wraps the shoulders the same way): from 60 mm above the top of the tallest
mark (PALA, z 0.74) over the corner radius to 50 mm from the centre line. Numbers and the rejected sites: site_scan1912.py.
The inner face and the well are dark (`cockpit`, the fuselage's own inner-face finish) with raised frames / stringers (`structure`, the
project's internals look) and two hinge arms (`metal_dark`).

What is built, per side (L / R), all derived from the real fus_rear paint faces of the model given on the command line:
  airbrake_<S>_hinge  EMPTY on the hinge axis: a straight line in the plane of the front edge, parallel to the chord of the (curved) front
                      edge and half the edge's sagitta outside it (so, fully open, the middle of the front edge dips under the skin ahead
                      and the two corners lift by the same small amount). Local axes (Blender): x = hinge line (up / inboard on the left
                      side, the opposite on the right), y = forward along the skin, z = outward. Unity (x, z, y swap): X = hinge line,
                      Y = outward, Z = forward, i.e. the stock Airbrake rotation (+maxAngle about local X) swings the aft (-Z) edge outward (+Y).
  airbrake_<S>_axis / airbrake_<S>_out   EMPTY markers 1 m from the hinge along the hinge line / outward: GA25XBuild.cs builds the hinge
                      frame from these three POSITIONS (it does not trust imported rotations); they are not kept in the prefab.
  airbrake_<S>        MESH child of the hinge. Outer face = the skin faces under the panel, cut to the panel outline, pushed PROUD along
                      the skin normals, material `paint` inside a 7 mm dark band (the seam of the shut panel), livery UV = the atlas UV of
                      the skin point under each vertex (same texels as the skin beneath; nothing is packed, the atlas is not touched).
                      Rim, inner face, frames, stringers and hinge arms reach INTO the fuselage when shut (hidden behind the uncut skin).
  airbrake_tray_<S>   MESH, fixed (child of fus_rear in Unity): dark well floor above the skin with frames / stringers, a little smaller
                      than the panel; inside the shut panel's box, visible only when the panel is open.
No collider, no part: the owning part's mesh is not changed.

  blender --background assets/model_ga25x/ga25x.blend --python blender/ga25x/airbrake1912.py -- --out <dir>
      -> <dir>/ga25x_airbrake.blend (GA25X_root + the ten objects only), <dir>/ga25x_airbrake.json (numbers for the checks / stubs)
  The runner blender/ga25x/run_airbrake1912.py then exports the FBX with the project's own exporter and runs the checks.

Pure-python core first (no bpy): the stub tests import it.
"""
import math, json, os, sys

# ---------------------------------------------------------------- the design numbers (Blender frame: nose +Y, up +Z, right wing +X)
# Outline on the shoulder: front edge (hinge) and aft edge at constant y, lower edge at constant z, upper edge at constant |x|.
SITE = dict(y_hinge=-4.20, y_aft=-5.80, z_lo=0.80, x_in=0.05)
MARKS = dict(y=-4.9, z=0.24, BDF=(1.30, 0.76), PALA=(0.98, 1.00))     # faction marks on the flank (read from the livery composer, for the check)
MARK_CLEAR = 0.05     # the lower panel edge is at least this far above the top of the tallest mark
AXIS_FRAC = 0.5       # hinge axis: this share of the front edge's sagitta outside its chord
PROUD = 0.0049        # outer (paint) face above the skin
TRAY = 0.0020         # well floor above the skin (the green strips' proven 2 mm)
STRINGER = 0.0030     # well frames / stringers above the skin (1.9 mm under the shut panel face)
SEAM = 0.007          # dark band round the outer face (the shut panel's seam line; the livery's own panel lines are 5 mm)
DEPTH = 0.022         # inner face below the skin (inside the fuselage when shut)
RIB_EDGE, RIB_STR, RIB_FRAME, RIB_ARM = 0.028, 0.024, 0.018, 0.050    # relief of the edge frame / stringers / cross frames / hinge arms on the inner face (all different: no coplanar tops)
RIB_W = 0.034         # width of a frame / stringer
EDGE_IN = 0.012       # inner structure and well floor inside the panel outline
TRAY_HINGE_IN = 0.020
TRI_PANEL_MAX, TRI_TRAY_MAX = 2100, 560     # triangle budget per panel / per well (check rows)
AHEAD_MAX = 0.05      # opening: the curved front lip rides over the fixed skin ahead of the straight hinge line by at most this (check row; measured 44 mm)
DEEP_MAX = 0.14       # fully open: the part of the panel still inside the fuselage ends this close to the hinge line (check row)
MAX_ANGLE = 55.0      # deg (Airbrake.maxAngle)
OPEN_SPEED = 1.0      # 1 / s (Airbrake.openSpeed)
DRAG_AMOUNT = 2.0     # Airbrake.dragAmount (supervisor decision)
MAT_FACE, MAT_RIB, MAT_ARM = 'cockpit', 'structure', 'metal_dark'   # inner face + well floor / frames + stringers / seam, rim, hinge arms
# What the Unity build really draws these with (sRGB 0-1; read 2026-11-15, for the renders and the stub test, not used by the build):
#   cockpit    GA25XBuild.cs BuildMaterials: URP Lit, plain colour (0.20, 0.205, 0.215), metallic 0.1, smoothness 0.25 (the fuselage inner faces)
#   structure  StockStructure.Apply moves every `structure` submesh into a child renderer <name>_struct drawn with GA25X_structure_look:
#              URP Lit, the game's aircraft_structure_b (mean 189 / 255) x base 0.80 = light grey about 0.59, metallic 0.10
#              (this is why the first build's all-`structure` inner face was a pale board in game)
#   metal_dark GA25XBuild.cs: URP Lit, tile b25h_metal_dark_b (mean 22 / 255), metallic 0.7
GAME_COLOURS = dict(cockpit=(0.20, 0.205, 0.215), structure=(0.59, 0.59, 0.59), metal_dark=(0.086, 0.087, 0.092))
EPS = 1e-6


def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def mul(a, k): return (a[0] * k, a[1] * k, a[2] * k)
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def norm(a):
    l = math.sqrt(dot(a, a))
    return (a[0] / l, a[1] / l, a[2] / l) if l > 0 else (0.0, 0.0, 0.0)


def plane(n, d, snap=None):
    """half space: keep dot(n, p) >= d. snap = (axis, bound) for an axis-aligned plane (cut points get the exact bound)."""
    return (tuple(n), d, snap)


def ax(axis, bound, greater):
    n = [0.0, 0.0, 0.0]
    n[axis] = 1.0 if greater else -1.0
    return plane(n, bound if greater else -bound, (axis, bound))


def clip(poly, pl):
    """Sutherland-Hodgman against one plane. poly = [(pos3, uv2)], convex. Position and UV are interpolated together."""
    n, d, snap = pl
    out = []
    m = len(poly)
    for i in range(m):
        a, b = poly[i], poly[(i + 1) % m]
        da, db = dot(n, a[0]) - d, dot(n, b[0]) - d
        if da >= -EPS:
            out.append(a)
        if (da > EPS and db < -EPS) or (da < -EPS and db > EPS):
            t = da / (da - db)
            p = tuple(a[0][k] + (b[0][k] - a[0][k]) * t for k in range(3))
            if snap is not None:
                p = tuple(snap[1] if k == snap[0] else p[k] for k in range(3))
            uv = tuple(a[1][k] + (b[1][k] - a[1][k]) * t for k in range(2))
            out.append((p, uv))
    res = []
    for q in out:                      # drop repeated points
        if not res or max(abs(q[0][k] - res[-1][0][k]) for k in range(3)) > 1e-7:
            res.append(q)
    if len(res) > 1 and max(abs(res[0][0][k] - res[-1][0][k]) for k in range(3)) <= 1e-7:
        res.pop()
    return res if len(res) >= 3 else []


def clip_all(poly, planes):
    for pl in planes:
        poly = clip(poly, pl)
        if not poly:
            return []
    return poly


def region(site, side, e=0.0, e_hinge=None):
    """the panel outline as half spaces, shrunk by e on every edge (e_hinge at the hinge edge):
    [front (hinge) edge, aft edge, lower edge (constant z), upper edge (constant |x|, beside the centre line)]"""
    eh = e if e_hinge is None else e_hinge
    return [ax(1, site['y_hinge'] - eh, False), ax(1, site['y_aft'] + e, True), ax(2, site['z_lo'] + e, True), ax(0, side * (site['x_in'] + e), side > 0)]


def slab(axis, origin, a, b):
    """a <= dot(axis, p - origin) <= b"""
    o = dot(axis, origin)
    return [plane(axis, o + a), plane(mul(axis, -1.0), -(o + b))]


def poly_normal(pts):
    n = [0.0, 0.0, 0.0]
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        n[0] += (a[1] - b[1]) * (a[2] + b[2]); n[1] += (a[2] - b[2]) * (a[0] + b[0]); n[2] += (a[0] - b[0]) * (a[1] + b[1])
    return norm(n)


def poly_area(pts):
    n = [0.0, 0.0, 0.0]
    for i in range(1, len(pts) - 1):
        c = cross(sub(pts[i], pts[0]), sub(pts[i + 1], pts[0]))
        n = [n[k] + c[k] for k in range(3)]
    return 0.5 * math.sqrt(dot(n, n))


def key(p):
    return (round(p[0], 5), round(p[1], 5), round(p[2], 5))


def skin_patch(skin_tris, planes):
    """skin triangles [(pos3, uv2) x 3] (outward winding) -> ([polygons [(pos3, uv2)]], {key: averaged unit normal})"""
    polys = []
    acc = {}
    for tri in skin_tris:
        p = clip_all(list(tri), planes)
        if not p:
            continue
        pts = [q[0] for q in p]
        a = poly_area(pts)
        if a < 1e-9:
            continue
        n = poly_normal([q[0] for q in tri])
        polys.append(p)
        for q in pts:
            k = key(q)
            v = acc.setdefault(k, [0.0, 0.0, 0.0])
            for i in range(3):
                v[i] += n[i] * a
    return polys, {k: norm(v) for k, v in acc.items()}


def skin_patches(skin_tris, plane_sets):
    """several outlines at once -> ([polygon list per outline], one normal map for all their points)"""
    res, acc = [], {}
    for ps in plane_sets:
        polys, n = skin_patch(skin_tris, ps)
        res.append(polys)
        for k, v in n.items():
            a = acc.setdefault(k, [0.0, 0.0, 0.0])
            for i in range(3):
                a[i] += v[i]
    return res, {k: norm(v) for k, v in acc.items()}


def boundary_edges(polys):
    """directed edges (a, b) of the patch outline (edges used by exactly one polygon), in each polygon's own winding"""
    cnt = {}
    for p in polys:
        for i in range(len(p)):
            a, b = key(p[i][0]), key(p[(i + 1) % len(p)][0])
            cnt[(a, b)] = (p[i][0], p[(i + 1) % len(p)][0])
    return [v for (a, b), v in cnt.items() if (b, a) not in cnt]


def boundary_loops(polys):
    """number of closed loops the patch outline makes (1 = one patch without a hole); -1 = the outline does not close"""
    nxt = {}
    for a, b in boundary_edges(polys):
        if key(a) in nxt:
            return -1
        nxt[key(a)] = key(b)
    loops = 0
    while nxt:
        s = k = next(iter(nxt))
        while True:
            k2 = nxt.pop(k, None)
            if k2 is None:
                return -1
            k = k2
            if k == s:
                break
        loops += 1
    return loops


def edge_axis(pts, side):
    """front / aft edge of the panel (points in one plane y = const) -> (lower end, upper end, in-plane outward unit normal of the
    chord, sagitta of the edge outside the chord)"""
    lo = min(pts, key=lambda q: (q[2], -abs(q[0])))
    hi = min(pts, key=lambda q: (abs(q[0]), -q[2]))
    c = norm(sub(hi, lo))
    n = (c[2], 0.0, -c[0])
    if n[0] * side + n[2] < 0:
        n = mul(n, -1.0)
    return lo, hi, n, max(dot(sub(q, lo), n) for q in pts)


def hinge_frame(side, front, aft):
    """front / aft: the skin points of the panel's front (hinge) and aft edge. -> ((origin, x_axis (hinge line), y_axis (forward along
    the skin), z_axis (outward)), numbers). Right-handed, Blender frame. The hinge line is parallel to the chord of the front edge,
    AXIS_FRAC of its sagitta outside it."""
    lo, hi, n, sag = edge_axis(front, side)
    o = add(mul(add(lo, hi), 0.5), mul(n, AXIS_FRAC * sag))
    lo2, hi2, n2, sag2 = edge_axis(aft, side)
    o2 = add(mul(add(lo2, hi2), 0.5), mul(n2, AXIS_FRAC * sag2))
    x = norm(sub(hi, lo))
    if side > 0:
        x = mul(x, -1.0)
    t = sub(o, o2)
    t = norm(sub(t, mul(x, dot(t, x))))
    z = cross(x, t)
    if dot(z, n) < 0.9:
        raise ValueError(f'hinge frame: outward axis {z} is not the outward normal of the front edge {n}')
    return (o, x, t, z), dict(chord=math.sqrt(dot(sub(hi, lo), sub(hi, lo))), sagitta=sag, aft_origin=o2,
                              tilt_deg=math.degrees(math.atan2(abs(n[2]), abs(n[0]))))


def to_local(p, fr):
    o, x, y, z = fr
    d = sub(p, o)
    return (dot(d, x), dot(d, y), dot(d, z))


def to_world(q, fr):
    o, x, y, z = fr
    return add(o, add(mul(x, q[0]), add(mul(y, q[1]), mul(z, q[2]))))


def open_local(q, deg):
    """panel-local point at Airbrake open angle `deg`. Unity: Rotate(+deg about local X) with Unity (X, Y, Z) = our local (x, z, y);
    in this right-handed local frame that is a rotation of -deg about x: the aft edge (y < 0) goes outward (z > 0)."""
    a = math.radians(-deg)
    c, s = math.cos(a), math.sin(a)
    return (q[0], q[1] * c - q[2] * s, q[1] * s + q[2] * c)


def unity_rotate_x(v_unity, deg):
    """the stock call transforms[j].Rotate(new Vector3(deg, 0, 0), Space.Self) applied to a hinge-local Unity vector (left-handed,
    positive angle about +X turns +Y toward +Z)"""
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    x, y, z = v_unity
    return (x, y * c - z * s, y * s + z * c)


def build_side(skin_tris, side, site=SITE):
    """skin_tris: fus_rear paint triangles of this half (world Blender coords + atlas UV). ->
    dict(frame, panel=[(local verts, uvs or None, mat)], tray=[(world verts, None, mat)], stats)"""
    y0, y1 = site['y_hinge'], site['y_aft']
    e = SEAM
    R0, R1 = region(site, side), region(site, side, e)
    b_front = [ax(1, y0, False), ax(1, y0 - e, True)] + R0[2:]
    b_aft = [ax(1, y1 + e, False), ax(1, y1, True)] + R0[2:]
    b_lo = R1[:2] + [ax(2, site['z_lo'], True), ax(2, site['z_lo'] + e, False), R0[3]]
    b_in = R1[:2] + [R1[2], R0[3], ax(0, side * (site['x_in'] + e), side < 0)]
    (polys, paint, p_front, p_aft, p_lo, p_in), nrm = skin_patches(skin_tris, (R0, R1, b_front, b_aft, b_lo, b_in))
    if not polys or not paint:
        raise ValueError('no skin under the panel outline')
    loops = boundary_loops(polys)
    if loops != 1:
        raise ValueError(f'the skin under the panel outline is not one closed patch ({loops} outline loops): a hole or a missing face under the panel')
    pts = [q[0] for p in polys for q in p]
    front = [q for q in pts if abs(q[1] - y0) < 1e-6]
    aft = [q for q in pts if abs(q[1] - y1) < 1e-6]
    if len(front) < 2 or len(aft) < 2:
        raise ValueError('the skin does not reach the front / aft edge of the outline')
    fr, hf = hinge_frame(side, front, aft)
    o, xa, ya, za = fr
    area3 = sum(poly_area([q[0] for q in p]) for p in polys)
    loc_skin = [to_local(q, fr) for q in pts]
    L = max(-q[1] for q in loc_skin)
    xs0, xs1 = min(q[0] for q in loc_skin), max(q[0] for q in loc_skin)
    loc_front = [to_local(q, fr) for q in front]
    fz0, fz1 = min(q[2] for q in loc_front), max(q[2] for q in loc_front)

    def off(q, d, n=nrm):
        return add(q, mul(n[key(q)], d))

    panel = []
    # outer face (skin winding): paint inside a dark seam band; inner face; rim
    for p in paint:
        panel.append(([to_local(off(q[0], PROUD), fr) for q in p], [q[1] for q in p], 'paint'))
    for band in (p_front, p_aft, p_lo, p_in):
        for p in band:
            panel.append(([to_local(off(q[0], PROUD), fr) for q in p], None, MAT_ARM))
    for p in polys:
        panel.append(([to_local(off(q[0], -DEPTH), fr) for q in reversed(p)], None, MAT_FACE))
    for a, b in boundary_edges(polys):
        panel.append(([to_local(off(b, PROUD), fr), to_local(off(a, PROUD), fr), to_local(off(a, -DEPTH), fr), to_local(off(b, -DEPTH), fr)], None, MAT_ARM))

    def rib(planes, h, mat):
        """raised member on the inner face: the skin strip inside `planes`, its top h below the inner face, with side walls"""
        sp, sn = skin_patch(skin_tris, planes)
        fs = []
        for p in sp:
            fs.append(([to_local(off(q[0], -(DEPTH + h), sn), fr) for q in reversed(p)], None, mat))
        for a, b in boundary_edges(sp):
            fs.append(([to_local(off(b, -DEPTH, sn), fr), to_local(off(a, -DEPTH, sn), fr), to_local(off(a, -(DEPTH + h), sn), fr), to_local(off(b, -(DEPTH + h), sn), fr)], None, mat))
        return fs

    RI = region(site, side, EDGE_IN)
    w = RIB_W
    # edge frame (four members), two stringers along the panel, three cross frames, two hinge arms
    panel += rib([ax(1, y0 - EDGE_IN, False), ax(1, y0 - EDGE_IN - w, True)] + RI[2:], RIB_EDGE, MAT_RIB)
    panel += rib([ax(1, y1 + EDGE_IN + w, False), ax(1, y1 + EDGE_IN, True)] + RI[2:], RIB_EDGE, MAT_RIB)
    panel += rib(RI[:2] + [RI[2], ax(2, site['z_lo'] + EDGE_IN + w, False), RI[3]], RIB_EDGE, MAT_RIB)
    panel += rib(RI[:2] + [RI[2], RI[3], ax(0, side * (site['x_in'] + EDGE_IN + w), side < 0)], RIB_EDGE, MAT_RIB)
    for f in (1 / 3, 2 / 3):
        xc = xs0 + f * (xs1 - xs0)
        panel += rib(RI + slab(xa, o, xc - w / 2, xc + w / 2), RIB_STR, MAT_RIB)
    for f in (0.25, 0.5, 0.75):
        panel += rib(RI + slab(ya, o, -f * L - w / 2, -f * L + w / 2), RIB_FRAME, MAT_RIB)
    for f in (0.18, 0.82):
        xc = xs0 + f * (xs1 - xs0)
        panel += rib(region(site, side, EDGE_IN, 0.0) + slab(xa, o, xc - 0.022, xc + 0.022) + slab(ya, o, -0.42, 0.05), RIB_ARM, MAT_ARM)
    # fixed well: floor + frames / stringers, conformal to the skin
    RT = region(site, side, EDGE_IN, TRAY_HINGE_IN)
    tray = []
    tp, tn = skin_patch(skin_tris, RT)
    for p in tp:
        tray.append(([add(q[0], mul(tn[key(q[0])], TRAY)) for q in p], None, MAT_FACE))

    def strip(planes):
        sp, sn = skin_patch(skin_tris, planes)
        for p in sp:
            tray.append(([add(q[0], mul(sn[key(q[0])], STRINGER)) for q in p], None, MAT_RIB))

    RS = region(site, side, EDGE_IN + 0.02, TRAY_HINGE_IN + 0.02)
    for f in (0.2, 0.5, 0.8):
        xc = xs0 + f * (xs1 - xs0)
        strip(RS + slab(xa, o, xc - 0.016, xc + 0.016))
    for f in (0.2, 0.4, 0.6, 0.8):
        strip(RS + slab(ya, o, -f * L - 0.013, -f * L + 0.013))
    free = to_local(hf['aft_origin'], fr)
    free = (free[0], free[1], free[2] + PROUD)
    c55 = math.cos(math.radians(MAX_ANGLE)); s55 = math.sin(math.radians(MAX_ANGLE))
    stats = dict(side='L' if side < 0 else 'R', length=round(L, 4), girth=round(area3 / (y0 - y1), 4), chord=round(hf['chord'], 4), area_m2=round(area3, 4),
                 sagitta_mm=round(hf['sagitta'] * 1000, 1), hinge_tilt_deg=round(hf['tilt_deg'], 2),
                 front_edge_local_mm=[round(fz0 * 1000, 1), round(fz1 * 1000, 1)],
                 front_dip_open_mm=round(max(fz1, 0.0) * (1 - c55) * 1000, 1), front_lift_open_mm=round(max(-fz0, 0.0) * (1 - c55) * 1000, 1),
                 paint_polys=len(paint),
                 free_edge_local=[round(a, 5) for a in free],
                 free_edge_open_local=[round(a, 5) for a in open_local(free, MAX_ANGLE)])
    return dict(frame=fr, panel=panel, tray=tray, stats=stats, paint=[[(q[0], q[1]) for q in p] for p in paint], normals=nrm)


def tri_count(faces):
    return sum(len(f[0]) - 2 for f in faces)


def unity(v):                 # Blender vector -> Unity (x right, y up, z forward)
    return (v[0], v[2], v[1])


# ============================================================================================ Blender side
def _skin_tris(ob, side, site):
    import bpy  # noqa: F401
    me = ob.data
    M = ob.matrix_world
    N3 = M.to_3x3()
    pi = {i for i, m in enumerate(me.materials) if m is not None and m.name == 'paint'}
    uv = me.uv_layers['livery'].data
    tris = []
    y0, y1 = site['y_hinge'] + 0.35, site['y_aft'] - 0.35
    for p in me.polygons:
        if p.material_index not in pi:
            continue
        c = M @ p.center
        n = (N3 @ p.normal).normalized()
        # outer skin only: the face looks away from the fuselage axis (about z 0.30 here)
        if not (y1 < c.y < y0) or c.z < site['z_lo'] - 0.4 or n.x * c.x + n.z * (c.z - 0.30) < 0.2 * math.hypot(c.x, c.z - 0.30):
            continue
        loops = list(p.loop_indices)
        pts = [(tuple(M @ me.vertices[me.loops[li].vertex_index].co), tuple(uv[li].uv)) for li in loops]
        if max(q[0][0] * side for q in pts) < 0.0:
            continue
        for k in range(1, len(pts) - 1):
            tris.append((pts[0], pts[k], pts[k + 1]))
    return tris


def _mesh(name, faces, mats, detail_axes):
    """faces [(verts, uvs or None, mat)] -> mesh with UV layers livery + detail (0.5 per metre, as the model)"""
    import bpy
    me = bpy.data.meshes.new(name)
    names = []
    for f in faces:
        if f[2] not in names:
            names.append(f[2])
    names.sort(key=lambda n: 0 if n == 'paint' else 1)
    verts, polys, vmap = [], [], {}
    for vs, uvs, mat in faces:
        idx = []
        for v in vs:
            k = (mat == 'paint', round(v[0], 6), round(v[1], 6), round(v[2], 6)) if mat == 'paint' else None
            if k is not None and k in vmap:
                idx.append(vmap[k])
            else:
                if k is not None:
                    vmap[k] = len(verts)
                idx.append(len(verts))
                verts.append(v)
        polys.append(idx)
    me.from_pydata(verts, [], polys)
    for n in names:
        me.materials.append(mats[n])
    lv = me.uv_layers.new(name='livery')
    dv = me.uv_layers.new(name='detail')
    a, b = detail_axes
    for poly, (vs, uvs, mat) in zip(me.polygons, faces):
        poly.material_index = names.index(mat)
        poly.use_smooth = mat == 'paint'
        for j, li in enumerate(poly.loop_indices):
            lv.data[li].uv = uvs[j] if uvs is not None else (0.0, 0.0)
            dv.data[li].uv = (vs[j][a] * 0.5, vs[j][b] * 0.5)
    me.update()
    if len(me.polygons) != len(faces):
        raise ValueError(f'{name}: {len(faces)} faces in, {len(me.polygons)} polygons out')
    return me


def build_objects(site=SITE, collection=None):
    """in the open scene (the GA-25X model): creates the six objects; returns (objects by name, report dict)"""
    import bpy
    from mathutils import Matrix, Vector
    O = bpy.data.objects
    fr_ob = O['fus_rear']
    root = O['GA25X_root']
    mats = {n: bpy.data.materials[n] for n in ('paint', MAT_FACE, MAT_RIB, MAT_ARM)}
    coll = collection or fr_ob.users_collection[0]
    C = root.matrix_world.translation
    objs, rep = {}, dict(site=site, proud=PROUD, tray=TRAY, depth=DEPTH, max_angle=MAX_ANGLE, open_speed=OPEN_SPEED, drag_amount=DRAG_AMOUNT,
                         cg_blender=[round(a, 4) for a in C], sides={})
    for side in (-1, 1):
        S = 'L' if side < 0 else 'R'
        tris = _skin_tris(fr_ob, side, site)
        r = build_side(tris, side, site)
        o, x, y, z = r['frame']
        Mh = Matrix(((x[0], y[0], z[0], o[0]), (x[1], y[1], z[1], o[1]), (x[2], y[2], z[2], o[2]), (0, 0, 0, 1)))
        h = O.new(f'airbrake_{S}_hinge', None)
        h.empty_display_size = 0.15
        coll.objects.link(h)
        h.parent = fr_ob
        h.matrix_world = Mh
        h['b25_info'] = json.dumps(dict(kind='airbrake_hinge', hinge_axis=[round(a, 6) for a in x], open_deg=-MAX_ANGLE,
                                        note='Unity local X = hinge line, Y = outward, Z = forward; stock Airbrake rotates +maxAngle about local X'))
        for nm, v, what in (('axis', x, 'hinge line'), ('out', z, 'outward normal')):      # frame markers: positions only (GA25XBuild.cs)
            m = O.new(f'airbrake_{S}_{nm}', None)
            m.empty_display_size = 0.05
            coll.objects.link(m)
            m.parent = fr_ob
            m.matrix_world = Matrix.Translation(Vector(add(o, v)))
            m['b25_info'] = json.dumps(dict(kind='airbrake_marker', note=f'1 m from airbrake_{S}_hinge along the {what}; build-time only, not in the prefab'))
            objs[m.name] = m
        p = O.new(f'airbrake_{S}', _mesh(f'airbrake_{S}', r['panel'], mats, (1, 0)))
        coll.objects.link(p)
        p.parent = h
        p.matrix_parent_inverse = Matrix.Identity(4)
        p.matrix_world = Mh
        p['b25_info'] = json.dumps(dict(kind='airbrake_panel', note='1.9.12 shoulder airbrake panel; paint = the atlas texels of the fus_rear skin under it; no collider, not a part'))
        t = O.new(f'airbrake_tray_{S}', _mesh(f'airbrake_tray_{S}', r['tray'], mats, (1, 2)))
        coll.objects.link(t)
        t.parent = fr_ob
        t.matrix_parent_inverse = Matrix.Identity(4)
        t.matrix_world = Matrix.Identity(4)
        t['b25_info'] = json.dumps(dict(kind='airbrake_tray', note='fixed well floor under the panel (child of fus_rear); visible only when the panel is open'))
        objs.update({h.name: h, p.name: p, t.name: t})
        st = dict(r['stats'])
        st['tris'] = dict(panel=tri_count(r['panel']), tray=tri_count(r['tray']))
        st['hinge_blender'] = [round(a, 5) for a in o]
        st['hinge_unity'] = [round(a, 5) for a in unity(sub(o, tuple(C)))]
        st['hinge_x_unity'] = [round(a, 6) for a in unity(x)]
        st['outward_unity'] = [round(a, 6) for a in unity(z)]
        st['forward_unity'] = [round(a, 6) for a in unity(y)]
        fo = to_world(open_local(tuple(st['free_edge_local']), MAX_ANGLE), r['frame'])
        fc = to_world(tuple(st['free_edge_local']), r['frame'])
        st['free_edge_closed_blender'] = [round(a, 4) for a in fc]
        st['free_edge_open_blender'] = [round(a, 4) for a in fo]
        # how far the free edge moves away from the aircraft's long axis through the CG (the Unity build measures the same)
        st['free_edge_outward_m'] = round(math.hypot(fo[0], fo[2] - C[2]) - math.hypot(fc[0], fc[2] - C[2]), 4)
        # paint vertices with their UV and the skin point under each (the stubs / the Unity row compare against the skin)
        pv = {}
        for poly in r['paint']:
            for q, uv in poly:
                pv[key(q)] = (q, uv, r['normals'][key(q)])
        st['paint_points'] = [dict(skin=[round(a, 5) for a in q], uv=[round(a, 7) for a in uv], n=[round(a, 5) for a in n]) for q, uv, n in pv.values()]
        rep['sides'][S] = st
    bpy.context.view_layer.update()
    return objs, rep


_REST = {}


def pose(deg):
    """rotate both hinge empties to the Airbrake open angle (0 = shut)"""
    import bpy
    from mathutils import Matrix
    for S in 'LR':
        h = bpy.data.objects[f'airbrake_{S}_hinge']
        if h.name not in _REST:
            _REST[h.name] = h.matrix_world.copy()
        h.matrix_world = _REST[h.name] @ Matrix.Rotation(math.radians(-deg), 4, 'X')
    bpy.context.view_layer.update()


def main():
    import bpy
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    out = os.path.abspath(argv[argv.index('--out') + 1])
    os.makedirs(out, exist_ok=True)
    src = bpy.data.filepath
    objs, rep = build_objects()
    rep['model'] = os.path.basename(src)
    import hashlib
    rep['model_sha12'] = hashlib.sha256(open(src, 'rb').read()).hexdigest()[:12]
    # keep only the root + our six objects; they hang on the root in the add-on file (Unity re-parents them under fus_rear)
    root = bpy.data.objects['GA25X_root']
    world = {n: o.matrix_world.copy() for n, o in objs.items()}
    for n in [k for k in objs if k not in ('airbrake_L', 'airbrake_R')]:
        objs[n].parent = root
        objs[n].matrix_parent_inverse = root.matrix_world.inverted()
        objs[n].matrix_world = world[n]
    keep = set(objs) | {'GA25X_root'}
    for o in list(bpy.data.objects):
        if o.name not in keep:
            bpy.data.objects.remove(o, do_unlink=True)
    bpy.context.view_layer.update()
    for n, o in objs.items():
        d = (o.matrix_world.translation - world[n].translation).length
        if d > 1e-6:
            raise SystemExit(f'{n} moved {d} m while re-parenting')
    with open(os.path.join(out, 'ga25x_airbrake.json'), 'w') as f:
        json.dump(rep, f, indent=1)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, 'ga25x_airbrake.blend'), compress=True, copy=True)
    print('[airbrake1912] ' + json.dumps({S: {k: v for k, v in st.items() if k != 'paint_points'} for S, st in rep['sides'].items()}))
    print('[airbrake1912] saved', os.path.join(out, 'ga25x_airbrake.blend'))


if __name__ == '__main__' and 'bpy' in sys.modules:
    main()
