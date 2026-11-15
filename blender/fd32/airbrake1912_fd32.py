"""Heritage Pairs 1.9.12: FD-32 airbrake panels (two small flank panels on fus_rear), built as an ADD-ON to the shipped model.

The main model (assets/model_fd32/fd32.blend / fd32.fbx) is only READ: the panels go into their own small FBX (fd32_airbrake.fbx, the
GA-25X 1.9.12 pattern) that FD32Build.cs adds under fus_rear when AirbrakePanels1912 is true. So with the flag off the aircraft is the
1.9.11 one byte for byte, the livery atlas is not re-packed and no existing texture is touched.

Site (resolved on the real model, Blender frame: nose +Y, up +Z, right wing +X; the two 1.9.12 studies disagreed):
  rejected  "one dorsal panel behind the hood" (airbrake_mechanism.md 5.3): the whole top line from the hood to the fin is the raised
            spine (spine_fwd / spine_aft) with the green spine strip on it.
  rejected  "flank y -2.12 .. -2.82, z -0.42 .. +0.04" (airbrake_panels.md 2.2): the faction mark of every livery sits at y -2.12,
            z -0.06 (build_textures_fd32.mark_sites: 0.58 m across) - the panel would cut it in two.
  built     flank y -2.47 (hinge, front edge) .. -3.05, z -0.32 .. +0.05: aft of the faction mark, 57 mm under the green side strip
            (z 0.107 .. 0.132, y -2.05 .. -2.90), ahead of the serial / naval title (from y -3.07), above the flare ejectors
            (+-0.20, -3.00, -0.50) and the hook slot (belly centre line), below the spine fairing, 1.05 m ahead of the tailplane.
            check_airbrake1912_fd32.py measures every one of these on the model.

What is built, per side (L / R), all derived from the real fus_rear paint faces of the model given on the command line:
  airbrake_<S>_hinge  EMPTY on the hinge line (vertical, through the outermost point of the panel's front edge, mid height). Local
                      axes (Blender): x = hinge line (up on the left side, down on the right), y = forward along the skin, z = outward.
                      Unity (x, z, y swap): X = hinge line, Y = outward, Z = forward: the stock Airbrake rotation (+maxAngle about
                      local X) swings the aft (-Z) edge outward (+Y).
  airbrake_<S>        MESH child of the hinge. Outer face = the skin faces under the panel, cut to the outline, pushed PROUD along the
                      skin normals; material `paint` inside a dark seam band, livery UV = the atlas UV of the skin point under each
                      vertex (the same texels as the skin beneath: every livery, also a player's own skin, is on the panel without a
                      re-bake). Seam band, rim and hinge knuckles: `cove` (dark matte, round 2). Inner face, stiffeners: `structure`; hinge arms: `metal_dark`; the inner body
                      reaches INTO the fuselage when shut (hidden behind the uncut skin), so the open panel has thickness.
  airbrake_tray_<S>   MESH, fixed (child of fus_rear in Unity): dark matte well floor (`cove`) on the skin with light stringers (`structure`), a little smaller
                      than the panel; inside the shut panel's box, visible only when the panel is open.
No collider, no part: fus_rear's own mesh (= its collider source) is not changed.

  blender --background assets/model_fd32/fd32.blend --python blender/fd32/airbrake1912_fd32.py -- --out <dir>
      -> <dir>/fd32_airbrake.blend (FD32_root + the six objects only), <dir>/fd32_airbrake.json (frames + numbers: FD32Build.cs, the
         checks and the stubs read it)
  blender/fd32/run_airbrake1912_fd32.py runs this, the FBX export, the checks and the renders.

Pure-python core first (no bpy): tools/stub_tests_1912_fd32.py imports it.
"""
import math, json, os, sys

AIRBRAKE_PANELS_1912 = True          # the Unity switch is FD32Build.AirbrakePanels1912; this one only stops the add-on being built

# ---------------------------------------------------------------- design numbers
SITE = dict(y_hinge=-2.47, y_aft=-3.05, z_lo=-0.32, z_hi=0.05)
PROUD = 0.0042        # outer (paint) face above the skin
TRAY = 0.0020         # well floor above the skin
STRINGER = 0.0032     # well stringers above the skin
SEAM = 0.005          # dark band round the outer face (the shut panel's seam line; the livery's own panel lines are 2-3 mm)
DEPTH = 0.012         # inner face below the skin (inside the fuselage when shut)
RIB_H = 0.008         # stiffener height on the inner face
ARM_DEEP = 0.014      # hinge arms: extra depth at the hinge line
KNUCKLE = 0.0035      # hinge knuckles above the outer face
TRAY_INSET = (0.030, 0.010, 0.010)   # tray edge inside the panel outline: at the hinge, at the aft edge, top / bottom
MAX_ANGLE = 55.0      # deg (Airbrake.maxAngle; FS-20 / T/A-30 value)
OPEN_SPEED = 1.0      # 1 / s (Airbrake.openSpeed, every stock aircraft)
DRAG_AMOUNT = 0.5     # Airbrake.dragAmount (supervisor decision)
MIN_FREE_EDGE_OUT = 0.15
# round 2 (review: on PALA Matte Black the shut panel read as a pale outline with two grey hinge blocks): everything of the SHUT panel that
# is not livery paint - seam band, rim, hinge knuckles - is `cove` (Unity FD32_cove: sRGB 0.045, non-metallic, smoothness 0.1), darker than
# every livery and without the sky reflection a metal_dark (metallic 0.6, smoothness 0.45) rim or knuckle can show at a grazing angle.
# metal_dark stays on the hinge arms of the inner face (seen only when the panel is open).
RIM_MAT = 'cove'
KNUCKLE_MAT = 'cove'
OUTER_MATS = ('paint', 'cove')        # materials allowed on anything visible with the panel shut
EPS = 1e-6

# things the outline must stay clear of (Blender frame; the check script measures the real objects, these are for the stubs)
MARK = dict(y=-2.12, z=-0.06, size=0.58)                      # faction mark on the flank (build_textures_fd32.mark_sites: 2 R)
SERIAL = dict(y=-3.30, z=-0.02, h=0.09, n=5)                  # "FD-32" / "P-32" small serial (serials(), small=True)
SIDE_STRIP = dict(y=(-2.90, -2.05), z=(0.107, 0.132))         # slimelight_side_L/R
FLARE = (0.20, -3.00, -0.503)                                 # flare_L/R
PART_SPLIT_Y = -1.90                                          # fus_center | fus_rear


def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def mul(a, k): return (a[0] * k, a[1] * k, a[2] * k)
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def norm(a):
    l = math.sqrt(dot(a, a))
    return (a[0] / l, a[1] / l, a[2] / l) if l > 0 else (0.0, 0.0, 0.0)


def key(p):
    return (round(p[0], 5), round(p[1], 5), round(p[2], 5))


def clip(poly, axis, bound, keep_greater):
    """one axis-aligned plane against a convex polygon [(pos3, uv2)]; position and UV are interpolated together"""
    out = []
    sg = 1.0 if keep_greater else -1.0
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        da, db = (a[0][axis] - bound) * sg, (b[0][axis] - bound) * sg
        if da >= -EPS:
            out.append(a)
        if (da > EPS and db < -EPS) or (da < -EPS and db > EPS):
            t = da / (da - db)
            p = [a[0][k] + (b[0][k] - a[0][k]) * t for k in range(3)]
            p[axis] = bound
            out.append((tuple(p), tuple(a[1][k] + (b[1][k] - a[1][k]) * t for k in range(2))))
    res = []
    for q in out:
        if not res or max(abs(q[0][k] - res[-1][0][k]) for k in range(3)) > 1e-7:
            res.append(q)
    if len(res) > 1 and max(abs(res[0][0][k] - res[-1][0][k]) for k in range(3)) <= 1e-7:
        res.pop()
    return res if len(res) >= 3 else []


def clip_rect(poly, y0, y1, z0, z1):
    """keep y1 <= y <= y0 (y0 = front) and z0 <= z <= z1"""
    for axis, bound, greater in ((1, y0, False), (1, y1, True), (2, z0, True), (2, z1, False)):
        poly = clip(poly, axis, bound, greater)
        if not poly:
            return []
    return poly


def area_vec(pts):
    n = [0.0, 0.0, 0.0]
    for i in range(1, len(pts) - 1):
        c = cross(sub(pts[i], pts[0]), sub(pts[i + 1], pts[0]))
        n = [n[k] + 0.5 * c[k] for k in range(3)]
    return tuple(n)


def skin_patch(skin_tris, y0, y1, z0, z1):
    """skin triangles [(pos3, uv2) x 3] (outward winding) clipped to the outline -> ([polygons], {key: area-weighted normal sum})"""
    polys, acc = [], {}
    for tri in skin_tris:
        p = clip_rect(list(tri), y0, y1, z0, z1)
        if not p:
            continue
        av = area_vec([q[0] for q in p])
        if math.sqrt(dot(av, av)) < 1e-9:
            continue
        polys.append(p)
        for q in p:
            v = acc.setdefault(key(q[0]), [0.0, 0.0, 0.0])
            for i in range(3):
                v[i] += av[i]
    return polys, acc


def patches(skin_tris, rects):
    """several outlines at once -> ([polygon list per rect], one unit-normal map for all their points)"""
    res, acc = [], {}
    for r in rects:
        polys, n = skin_patch(skin_tris, *r)
        res.append(polys)
        for k, v in n.items():
            a = acc.setdefault(k, [0.0, 0.0, 0.0])
            for i in range(3):
                a[i] += v[i]
    return res, {k: norm(v) for k, v in acc.items()}


def boundary_edges(polys):
    cnt = {}
    for p in polys:
        for i in range(len(p)):
            cnt[(key(p[i][0]), key(p[(i + 1) % len(p)][0]))] = (p[i][0], p[(i + 1) % len(p)][0])
    return [v for (a, b), v in cnt.items() if (b, a) not in cnt]


def to_local(p, fr):
    o, x, y, z = fr
    d = sub(p, o)
    return (dot(d, x), dot(d, y), dot(d, z))


def to_world(q, fr):
    o, x, y, z = fr
    return add(o, add(mul(x, q[0]), add(mul(y, q[1]), mul(z, q[2]))))


def open_local(q, deg):
    """panel-local point (x hinge, y forward, z outward; right-handed) at Airbrake angle `deg`. The stock call is Unity
    Rotate(+deg about local X) with Unity (X, Y, Z) = our (x, z, y); here that is a rotation of -deg about x: aft points (y < 0) go
    outward (z > 0)."""
    a = math.radians(-deg)
    c, s = math.cos(a), math.sin(a)
    return (q[0], q[1] * c - q[2] * s, q[1] * s + q[2] * c)


def unity_rotate_x(v, deg):
    """transforms[j].Rotate(new Vector3(deg, 0, 0), Space.Self) on a hinge-local Unity vector (left-handed: +X turns +Y toward +Z)"""
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return (v[0], v[1] * c - v[2] * s, v[1] * s + v[2] * c)


def unity(v):
    """Blender vector -> Unity (x right, y up, z forward)"""
    return (v[0], v[2], v[1])


def box(lo, hi, mat):
    x0, y0, z0 = lo; x1, y1, z1 = hi
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    idx = ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (1, 2, 6, 5), (3, 0, 4, 7))
    return [([v[i] for i in f], None, mat) for f in idx]


def wedge(x0, x1, y_h, y_a, z_top, z_h, z_a, mat):
    """hinge arm x0..x1 from the hinge (y_h, bottom z_h) tapering aft to y_a (bottom z_a), top at z_top; outward quads (y_h > y_a)"""
    v = [(x0, y_a, z_a), (x1, y_a, z_a), (x1, y_h, z_h), (x0, y_h, z_h), (x0, y_a, z_top), (x1, y_a, z_top), (x1, y_h, z_top), (x0, y_h, z_top)]
    idx = ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (1, 2, 6, 5), (3, 0, 4, 7))
    return [([v[i] for i in f], None, mat) for f in idx]


def tri_count(faces):
    return sum(len(f[0]) - 2 for f in faces)


def text_width(n, h):
    """width of an n-glyph word in the project's stroke font (tex_lib.glyph_segments)"""
    return (5.6 * n - 1.6) * h / 6.0


def outline_clearances(site=SITE):
    """distances (m, > 0 = clear) from the outline to the fixed things round it, from the design numbers alone (stubs); the check
    script repeats them on the real objects."""
    y0, y1, z0, z1 = site['y_hinge'], site['y_aft'], site['z_lo'], site['z_hi']
    return dict(part_split=PART_SPLIT_Y - y0,
                faction_mark=(MARK['y'] - MARK['size'] / 2) - y0,
                side_strip=SIDE_STRIP['z'][0] - z1,
                serial=y1 - (SERIAL['y'] + text_width(SERIAL['n'], SERIAL['h']) / 2 + 0.011),
                flare_z=z0 - FLARE[2])


def build_side(skin_tris, side, site=SITE):
    """skin_tris: fus_rear paint triangles of this flank (world Blender coords + atlas UV). ->
    dict(frame, panel=[(local verts, uvs or None, mat)], tray=[(world verts, None, mat)], stats, paint, normals)"""
    y0, y1, z0, z1 = site['y_hinge'], site['y_aft'], site['z_lo'], site['z_hi']
    e = SEAM
    (polys, paint, b_front, b_aft, b_lo, b_hi), nrm = patches(skin_tris, (
        (y0, y1, z0, z1), (y0 - e, y1 + e, z0 + e, z1 - e),
        (y0, y0 - e, z0, z1), (y1 + e, y1, z0, z1), (y0 - e, y1 + e, z0, z0 + e), (y0 - e, y1 + e, z1 - e, z1)))
    if not polys or not paint:
        raise ValueError('no skin under the panel outline')
    # the skin under the outline must be one closed sheet: its area projected on the side view = the outline rectangle
    proj = sum(abs(area_vec([q[0] for q in p])[0]) for p in polys)
    rect = (y0 - y1) * (z1 - z0)
    if abs(proj - rect) > 0.005 * rect:
        raise ValueError(f'skin under the outline: side-view area {proj:.5f} m2, outline {rect:.5f} m2 (a hole, a fold or a missing face)')
    if any(nrm[k][0] * side < 0.5 for k in nrm):
        raise ValueError('a skin normal under the outline does not face outward')
    pts = [q[0] for p in polys for q in p]
    zm = 0.5 * (z0 + z1)
    front = [q for q in pts if abs(q[1] - y0) < 1e-6]
    aft = [q for q in pts if abs(q[1] - y1) < 1e-6]
    def at_mid(edge, yv):
        """the skin point of a vertical outline edge at mid height (interpolated between its two nearest points: the same on both sides)"""
        lo_ = max((q for q in edge if q[2] <= zm), key=lambda q: q[2]); hi_ = min((q for q in edge if q[2] >= zm), key=lambda q: q[2])
        if hi_[2] - lo_[2] < 1e-9:
            return lo_, nrm[key(lo_)]
        f = (zm - lo_[2]) / (hi_[2] - lo_[2])
        return (lo_[0] + (hi_[0] - lo_[0]) * f, yv, zm), norm(add(mul(nrm[key(lo_)], 1 - f), mul(nrm[key(hi_)], f)))

    (pf, nf), (pa, na) = at_mid(front, y0), at_mid(aft, y1)
    t = norm((pf[0] - pa[0], y0 - y1, 0.0))                       # forward along the skin, level
    n = (t[1], -t[0], 0.0)
    if n[0] * side < 0:
        n = (-n[0], -n[1], 0.0)
    x = cross(t, n)                                               # hinge line: (0, 0, +1) on the left side, (0, 0, -1) on the right
    p0 = (pf[0], y0, zm)
    lift = max(dot(sub(add(q, mul(nrm[key(q)], PROUD)), p0), n) for q in front)
    o = add(p0, mul(n, lift))                                     # the hinge line touches the outermost point of the front edge
    fr = (o, x, t, n)
    xf = [abs(q[0]) for q in front]

    def off(q, d):
        return add(q, mul(nrm[key(q)], d))

    panel = []
    for p in paint:
        panel.append(([to_local(off(q[0], PROUD), fr) for q in p], [q[1] for q in p], 'paint'))
    for band in (b_front, b_aft, b_lo, b_hi):
        for p in band:
            panel.append(([to_local(off(q[0], PROUD), fr) for q in p], None, 'cove'))      # the seam: dark MATTE (metal_dark is a glossy metal, lighter than a black livery)
    for p in polys:
        panel.append(([to_local(off(q[0], -DEPTH), fr) for q in reversed(p)], None, 'structure'))
    for a, b in boundary_edges(polys):
        panel.append(([to_local(off(b, PROUD), fr), to_local(off(a, PROUD), fr), to_local(off(a, -DEPTH), fr), to_local(off(b, -DEPTH), fr)], None, RIM_MAT))
    loc = [to_local(q, fr) for q in pts]
    L = max(-q[1] for q in loc)
    hx = max(abs(q[0]) for q in loc)

    def skin_z(xc, ya, yb, hw=0.03):
        """lowest / highest local z of the skin points near height xc between local y ya..yb"""
        zs = [q[2] for q in loc if abs(q[0] - xc) <= hw and ya - 1e-6 <= q[1] <= yb + 1e-6]
        if not zs:
            zs = [q[2] for q in loc if abs(q[0] - xc) <= 3 * hw]
        return min(zs), max(zs)

    # two stiffeners along the panel and a closing frame at the aft edge (structure), two tapered hinge arms + two knuckles (metal_dark)
    for xc in (-0.50 * hx, 0.50 * hx):
        lo_, hi_ = skin_z(xc, -L, 0.0)
        panel += box((xc - 0.012, -L + 0.025, lo_ - DEPTH - RIB_H), (xc + 0.012, -0.04, lo_ - DEPTH + 0.002), 'structure')
    lo_, hi_ = skin_z(0.0, -L, -L + 0.06, hw=hx)
    panel += box((-hx + 0.015, -L + 0.010, lo_ - DEPTH - RIB_H), (hx - 0.015, -L + 0.030, lo_ - DEPTH + 0.002), 'structure')     # tops from the LOWEST skin point: never through the paint face
    for xc in (-0.22 * hx, 0.22 * hx):
        lo_, hi_ = skin_z(xc, -0.20, 0.0, hw=0.02)
        panel += wedge(xc - 0.011, xc + 0.011, -0.003, -0.20, lo_ - DEPTH + 0.002, lo_ - DEPTH - RIB_H - ARM_DEEP, lo_ - DEPTH - RIB_H + 0.003, 'metal_dark')
        lo_, hi_ = skin_z(xc, -0.03, 0.0, hw=0.02)
        panel += [f + ('knuckle',) for f in box((xc - 0.016, -0.028, lo_ + PROUD - 0.001), (xc + 0.016, -0.0015, hi_ + PROUD + KNUCKLE), KNUCKLE_MAT)]
    deep = min(v[2] for f in panel for v in f[0])
    # fixed well: floor + stringers, conformal to the skin
    ih, ia, iz = TRAY_INSET
    tray = []
    (tp,), tn = patches(skin_tris, ((y0 - ih, y1 + ia, z0 + iz, z1 - iz),))
    for p in tp:
        tray.append(([add(q[0], mul(tn[key(q[0])], TRAY)) for q in p], None, 'cove'))
    H = z1 - z0
    rects = [(y0 - ih - 0.015, y1 + ia + 0.015, z0 + f * H - 0.009, z0 + f * H + 0.009) for f in (0.25, 0.75)]
    yc = 0.5 * (y0 + y1)
    rects.append((yc + 0.009, yc - 0.009, z0 + iz + 0.015, z1 - iz - 0.015))
    sps, sn = patches(skin_tris, rects)
    for sp in sps:
        for p in sp:
            tray.append(([add(q[0], mul(sn[key(q[0])], STRINGER)) for q in p], None, 'structure'))
    aft_mid = to_local(add(pa, mul(na, PROUD)), fr)
    free = (0.0, aft_mid[1], aft_mid[2])
    fo = open_local(free, MAX_ANGLE)
    stats = dict(side='L' if side < 0 else 'R', length=round(L, 4), height=round(2 * hx, 4), area_side_view_m2=round(proj, 4),
                 front_edge_bow_mm=round((max(xf) - min(xf)) * 1000, 2), x_front=round(abs(pf[0]), 4), x_aft=round(abs(pa[0]), 4),
                 paint_polys=len(paint), inner_depth_mm=round(-deep * 1000, 2),
                 free_edge_local=[round(a, 5) for a in free], free_edge_open_local=[round(a, 5) for a in fo],
                 free_edge_outward_m=round(fo[2] - free[2], 4))
    return dict(frame=fr, panel=panel, tray=tray, stats=stats, paint=paint, normals=nrm)


# ============================================================================================ Blender side
def _skin_tris(ob, side, site):
    me = ob.data
    M = ob.matrix_world
    N3 = M.to_3x3()
    pi = {i for i, m in enumerate(me.materials) if m is not None and m.name == 'paint'}
    uv = me.uv_layers['livery'].data
    tris = []
    y0, y1 = site['y_hinge'] + 0.45, site['y_aft'] - 0.45
    for p in me.polygons:
        if p.material_index not in pi:
            continue
        c = M @ p.center
        n = (N3 @ p.normal).normalized()
        if not (y1 < c.y < y0) or n.x * side < 0.3 or c.x * side < 0.1:
            continue
        pts = [(tuple(M @ me.vertices[me.loops[li].vertex_index].co), tuple(uv[li].uv)) for li in p.loop_indices]
        for k in range(1, len(pts) - 1):
            tris.append((pts[0], pts[k], pts[k + 1]))
    return tris


def _mesh(name, faces, mats, detail_axes):
    """faces [(verts, uvs or None, mat)] -> mesh with the model's UV layers (livery, detail = 0.5 per metre); paint is slot 0"""
    import bpy
    me = bpy.data.meshes.new(name)
    names = sorted({f[2] for f in faces}, key=lambda n: (n != 'paint', n))
    verts, polys, vmap = [], [], {}
    for vs, uvs, mat, *_tag in faces:
        idx = []
        for v in vs:
            k = (round(v[0], 6), round(v[1], 6), round(v[2], 6)) if mat == 'paint' else None
            if k is not None and k in vmap:
                idx.append(vmap[k])
            else:
                if k is not None:
                    vmap[k] = len(verts)
                idx.append(len(verts)); verts.append(v)
        polys.append(idx)
    me.from_pydata(verts, [], polys)
    for n in names:
        me.materials.append(mats[n])
    lv = me.uv_layers.new(name='livery'); dv = me.uv_layers.new(name='detail')
    a, b = detail_axes
    for poly, (vs, uvs, mat, *_tag) in zip(me.polygons, faces):
        poly.material_index = names.index(mat)
        poly.use_smooth = mat == 'paint'
        for j, li in enumerate(poly.loop_indices):
            lv.data[li].uv = uvs[j] if uvs is not None else (0.0, 0.0)
            dv.data[li].uv = (vs[j][a] * 0.5, vs[j][b] * 0.5)
    me.update()
    if len(me.polygons) != len(faces):
        raise ValueError(f'{name}: {len(faces)} faces in, {len(me.polygons)} polygons out')
    return me


_HINGES = {}


def build_objects(site=SITE, collection=None):
    """in the open scene (the FD-32 model): creates the six objects; returns (objects by name, report dict)"""
    import bpy
    from mathutils import Matrix
    O = bpy.data.objects
    fus = O['fus_rear']; root = O['FD32_root']
    mats = {n: bpy.data.materials[n] for n in ('paint', 'structure', 'metal_dark', 'cove')}
    coll = collection or fus.users_collection[0]
    C = tuple(root.matrix_world.translation)
    objs = {}
    rep = dict(generator='blender/fd32/airbrake1912_fd32.py', aircraft='FD-32', site=site, proud=PROUD, tray=TRAY, stringer=STRINGER, seam=SEAM, depth=DEPTH,
               max_angle=MAX_ANGLE, open_speed=OPEN_SPEED, drag_amount=DRAG_AMOUNT, cg_blender=[round(a, 4) for a in C], owner='fus_rear',
               frame='Unity: x right, y up, z forward, origin = FD32_root (CG)', design_clearances=outline_clearances(site), sides={})
    for side in (-1, 1):
        S = 'L' if side < 0 else 'R'
        r = build_side(_skin_tris(fus, side, site), side, site)
        o, x, y, z = r['frame']
        Mh = Matrix(((x[0], y[0], z[0], o[0]), (x[1], y[1], z[1], o[1]), (x[2], y[2], z[2], o[2]), (0, 0, 0, 1)))
        h = O.new(f'airbrake_{S}_hinge', None); h.empty_display_size = 0.1
        coll.objects.link(h); h.parent = fus; h.matrix_world = Mh
        h['b25_info'] = json.dumps(dict(kind='airbrake_hinge', note='1.9.12: Unity local X = hinge line, Y = outward, Z = forward; the stock Airbrake rotates +maxAngle about local X (FD32Build builds this frame from fd32_airbrake.json)'))
        p = O.new(f'airbrake_{S}', _mesh(f'airbrake_{S}', r['panel'], mats, (1, 0)))
        coll.objects.link(p); p.parent = h; p.matrix_parent_inverse = Matrix.Identity(4); p.matrix_world = Mh
        p['b25_info'] = json.dumps(dict(kind='airbrake_panel', note='1.9.12 flank airbrake panel: paint = the atlas texels of the fus_rear skin under it; no collider, not a part'))
        t = O.new(f'airbrake_tray_{S}', _mesh(f'airbrake_tray_{S}', r['tray'], mats, (1, 2)))
        coll.objects.link(t); t.parent = fus; t.matrix_parent_inverse = Matrix.Identity(4); t.matrix_world = Matrix.Identity(4)
        t['b25_info'] = json.dumps(dict(kind='airbrake_tray', note='1.9.12 fixed well floor under the panel (child of fus_rear); seen only when the panel is open'))
        objs.update({h.name: h, p.name: p, t.name: t})
        _HINGES[h.name] = Mh.copy()
        st = dict(r['stats'])
        st['tris'] = dict(panel=tri_count(r['panel']), tray=tri_count(r['tray']))
        st['hinge_blender'] = [round(a, 5) for a in o]
        st['hinge_unity'] = [round(a, 5) for a in unity(sub(o, C))]
        st['hinge_x_unity'] = [round(a, 6) for a in unity(x)]
        st['forward_unity'] = [round(a, 6) for a in unity(y)]
        st['outward_unity'] = [round(a, 6) for a in unity(z)]
        fc = to_world(tuple(st['free_edge_local']), r['frame']); fo = to_world(tuple(st['free_edge_open_local']), r['frame'])
        st['free_edge_closed_blender'] = [round(a, 4) for a in fc]
        st['free_edge_open_blender'] = [round(a, 4) for a in fo]
        st['free_edge_gain_abs_x_m'] = round(abs(fo[0]) - abs(fc[0]), 4)
        # the same opening computed the Unity way (left-handed Rotate about local X on the Unity-frame vectors)
        fu = unity_rotate_x((st['free_edge_local'][0], st['free_edge_local'][2], st['free_edge_local'][1]), MAX_ANGLE)
        st['free_edge_open_local_unity_xyz'] = [round(a, 5) for a in fu]
        pv = {}
        for poly in r['paint']:
            for q, uv in poly:
                pv[key(q)] = (q, uv)
        st['paint_vertices'] = len(pv)
        st['paint_uv_box'] = [round(min(v[1][0] for v in pv.values()), 5), round(min(v[1][1] for v in pv.values()), 5),
                              round(max(v[1][0] for v in pv.values()), 5), round(max(v[1][1] for v in pv.values()), 5)]
        rep['sides'][S] = st
    return objs, rep


def pose(deg):
    """turn both hinges to Airbrake angle `deg` (0 = shut) exactly as the stock component does"""
    import bpy
    from mathutils import Matrix
    for name, Mh in _HINGES.items():
        bpy.data.objects[name].matrix_world = Mh @ Matrix.Rotation(math.radians(-deg), 4, 'X')
    bpy.context.view_layer.update()


def main():
    import bpy
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    out = os.path.abspath(argv[argv.index('--out') + 1])
    os.makedirs(out, exist_ok=True)
    if not AIRBRAKE_PANELS_1912:
        print('[fd32-airbrake] AIRBRAKE_PANELS_1912 is off: nothing built'); return
    src = bpy.data.filepath
    objs, rep = build_objects()
    keep = set(objs) | {'FD32_root'}
    for o in list(bpy.data.objects):
        if o.name not in keep:
            bpy.data.objects.remove(o, do_unlink=True)
    root = bpy.data.objects['FD32_root']
    from mathutils import Matrix
    for nme in ('airbrake_L_hinge', 'airbrake_R_hinge', 'airbrake_tray_L', 'airbrake_tray_R'):      # the owner (fus_rear) is gone: hang them on the root, world pose kept
        ob = objs[nme]; mw = _HINGES.get(nme, Matrix.Identity(4))
        ob.parent = root; ob.matrix_parent_inverse = root.matrix_world.inverted(); ob.matrix_world = mw
    bpy.context.view_layer.update()
    for blk in (bpy.data.meshes, bpy.data.images, bpy.data.materials):
        for d in list(blk):
            if d.users == 0:
                blk.remove(d)
    rep['source_model'] = os.path.basename(src)
    rep['tris_total'] = sum(v for s in rep['sides'].values() for v in s['tris'].values())
    with open(os.path.join(out, 'fd32_airbrake.json'), 'w') as f:
        json.dump(rep, f, indent=1)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, 'fd32_airbrake.blend'), compress=True, copy=True)
    print('[fd32-airbrake] ' + json.dumps({k: {a: b for a, b in v.items() if a in ('length', 'height', 'front_edge_bow_mm', 'tris', 'hinge_unity', 'free_edge_outward_m', 'inner_depth_mm')} for k, v in rep['sides'].items()}))
    print('[fd32-airbrake] saved', os.path.join(out, 'fd32_airbrake.blend'))


if __name__ == '__main__':
    main()
