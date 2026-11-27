"""Hawker Nimrod Mk I open cockpit, v2 (procedural; layout table in nimrod_ck_layout.py).

Layout from the user's photos refs\\nimrod_cockpit_user\\50.png (real Nimrod/Hart panel; references only, nothing copied) and 51-55
(game views of another Nimrod cockpit, used for the wall / floor / seat layout only):
  raised grey centre section (turn indicator on top, ASI + altimeter below) over a wide lower panel with a black tubular
  cross-frame; dials of several sizes with black / yellow / blue / white / chrome rims; brass fuel cocks, magneto switch box,
  data plate, cards, toggles; compass bowl under the panel; two Vickers breech casings either side of the upper section with
  brass feed blocks and wooden cocking knobs; slim black leather roll round the opening; tubular side frames with bracing
  wires; throttle quadrant (two levers) and red-orange trim wheel on the left; fuel cocks, priming pump, ammo counter box,
  oxygen regulator, fuel / oxygen lines and data cards on the right; dark red-brown floor with wooden footboards, rudder bar
  with stirrup pedals, spade-grip column on a torque tube; riveted aluminium bucket seat with a Sutton harness.
  One compact retrofit tac screen (mfd_center) on the lower panel centre (2082 setting); HUD kept (Unity side).

Props are separate named objects (cockpit_<prop>) so single props can be swapped later. Materials: ck_* tiling textures
(detail UV) + two own-UV atlases: `gauges` (dial faces, rims, needles) and `ck_art` (panel faces, placards, seat skin).

Movers (B25H.Instruments NIMROD1 branch, names unchanged from v1): gauge_<id>_needle / _needle_short / gauge_slip_needle /
gauge_compass_card; local +X (Unity) toward the pilot (compass: +X up); rest pose = the scale's first value (the needle mesh
points at the face's zero mark, see nimrod_ck_layout.DIALS zero), + angle = clockwise as seen by the pilot.
Stock drivers: cockpit_stick (Cockpit.Joystick), cockpit_rudderbar (ControlSurface yaw), cockpit_throttle (Cockpit.Throttle).
"""
import math
import bmesh
from mathutils import Vector, Quaternion, Matrix
from mathutils.geometry import tessellate_polygon
from b25h_geom import V, MeshBuf, loft, cylinder, box, circle_pts, fan_cap, oriented_quad, annulus, ear_clip
from b25h_parts import Part
import nimrod_spec as S
import nimrod_ck_layout as L
from nimrod_parts import fus_ring, frame_x

T_ = math.radians(L.TILT_DEG)
PN = V((0, -math.cos(T_), math.sin(T_)))      # panel normal toward the pilot
PU = V((0, math.sin(T_), math.cos(T_)))       # panel up
X_ = V((1, 0, 0))
P0 = V((0, L.PANEL_Y0, L.PANEL_Z0))
GAUGES = L.DIALS                                # (kept name: build_nimrod / docs refer to NC.GAUGES)
SCALES = L.SCALES
TAC = L.TAC
YA, YB = -1.28, -0.22                           # cockpit bay: aft bulkhead / forward (fuel tank) bulkhead
FOOT_Z = -0.28                                  # footwell roof under the fuel tank
FW_Y = -0.03                                    # footwell front wall (2026-11-22: was +0.02, 20 mm past the y 0 break)


# =========================================================================================== small helpers
def pp(x, h, off=0.0):
    return P0 + X_ * x + PU * h + PN * off


def face_o(mb, pts, mat, toward, uv=None, smooth=False):
    """polygon from points, oriented so its normal points along `toward`."""
    pts = [V(p) for p in pts]
    n = V()
    for i in range(1, len(pts) - 1):
        n += (pts[i] - pts[0]).cross(pts[i + 1] - pts[0])
    if n.dot(V(toward)) < 0:
        pts = pts[::-1]
        uv = uv[::-1] if uv else uv
    mb.poly(pts, mat, uv, smooth)


def strip(mb, A, B, mat, uv=None, outward_of=None, inward=False, closed=True, smooth=True):
    """quads between two rings; normals away from (or toward) the axis point `outward_of` (or each quad's own ring centre)."""
    n = len(A)
    segs = n if closed else n - 1
    ca = sum(A, V()) / n
    for j in range(segs):
        j1 = (j + 1) % n
        q = [A[j], A[j1], B[j1], B[j]]
        c = sum(q, V()) / 4
        ref = outward_of if outward_of is not None else ca
        d = c - ref
        # remove the axial component when the rings are coaxial: use the ring-plane radial direction
        nrm = (q[1] - q[0]).cross(q[3] - q[0])
        if nrm.length < 1e-12:
            continue
        s = nrm.dot(d)
        if (s < 0) != inward:
            q = q[::-1]
        mb.poly(q, mat, [uv] * 4 if uv else None, smooth)


def disc_face(mb, c, rt, up, r, region, n, N=32, mat='gauges', rot_deg=0.0):
    """flat disc (fan) with the gauge-atlas region mapped on it; rot_deg rotates the art (clockwise as seen along -n)."""
    ci = mb.v(c)
    a0 = math.radians(rot_deg)
    pts = [(math.cos(2 * math.pi * k / N), math.sin(2 * math.pi * k / N)) for k in range(N)]
    vi = [mb.v(c + (rt * x + up * y) * r) for x, y in pts]
    def uvp(x, y):
        # art rotation: a point at angle t on the mesh shows the art at t - rot (clockwise)
        xr = x * math.cos(a0) + y * math.sin(a0)
        yr = -x * math.sin(a0) + y * math.cos(a0)
        return L.gauge_uv(region, xr, yr)
    for k in range(N):
        tri = [ci, vi[k], vi[(k + 1) % N]]
        P = [mb.verts[t] for t in tri]
        uvs = [L.gauge_uv(region, 0, 0), uvp(*pts[k]), uvp(*pts[(k + 1) % N])]
        if (P[1] - P[0]).cross(P[2] - P[0]).dot(n) < 0:
            tri, uvs = [tri[0], tri[2], tri[1]], [uvs[0], uvs[2], uvs[1]]
        mb.face(tri, mat, uvs, False)


def lathe(mb, prof, c, axis, mat, N=16, ref=None, cap0=True, cap1=True, smooth=True, uv=None):
    """surface of revolution: prof = [(radius, t along axis)], radii > 0; outward normals; optional end caps."""
    ax = V(axis).normalized()
    c = V(c)
    rings = [circle_pts(c + ax * t, ax, r, N, ref) for r, t in prof]
    for A, B, (ra, ta), (rb, tb) in zip(rings, rings[1:], prof, prof[1:]):
        strip(mb, A, B, mat, uv, outward_of=None)
    if cap0:
        face_o(mb, rings[0], mat, -ax if prof[1][1] >= prof[0][1] else ax, [uv] * N if uv else None)
    if cap1:
        face_o(mb, rings[-1], mat, ax if prof[-1][1] >= prof[-2][1] else -ax, [uv] * N if uv else None)
    return rings


def tube_line(mb, pts, r, mat, N=8, closed=False, cap=True, smooth=True, ref=None, scale=None):
    """tube along a polyline (parallel-transported rings); scale = (sx, sy) for an elliptic section (sx along ref)."""
    P = [V(p) for p in pts]
    n = len(P)
    tang = []
    for i in range(n):
        if closed:
            t = (P[(i + 1) % n] - P[i - 1])
        else:
            t = (P[min(i + 1, n - 1)] - P[max(i - 1, 0)])
        tang.append(t.normalized())
    rv = V(ref) if ref is not None else (V((0, 0, 1)) if abs(tang[0].z) < 0.9 else V((1, 0, 0)))
    rings = []
    u = (rv - tang[0] * rv.dot(tang[0])).normalized()
    for i in range(n):
        if ref is not None:
            u = (rv - tang[i] * rv.dot(tang[i]))
            u = u.normalized() if u.length > 1e-6 else u
        else:
            u = (u - tang[i] * u.dot(tang[i])).normalized()
        w = tang[i].cross(u)
        sx, sy = scale if scale else (1.0, 1.0)
        rings.append([P[i] + (u * (math.cos(2 * math.pi * k / N) * sx) + w * (math.sin(2 * math.pi * k / N) * sy)) * r for k in range(N)])
    seq = rings + ([rings[0]] if closed else [])
    for A, B, a, b in zip(seq, seq[1:], P + ([P[0]] if closed else []), (P + ([P[0]] if closed else []))[1:]):
        nq = len(A)
        for j in range(nq):
            j1 = (j + 1) % nq
            q = [A[j], A[j1], B[j1], B[j]]
            c = sum(q, V()) / 4
            m = (a + b) / 2
            nrm = (q[1] - q[0]).cross(q[3] - q[0])
            if nrm.dot(c - m) < 0:
                q = q[::-1]
            mb.poly(q, mat, None, smooth)
    if cap and not closed:
        face_o(mb, rings[0], mat, -tang[0])
        face_o(mb, rings[-1], mat, tang[-1])
    return rings


def bm_dump(mb, bm, mat, face_mat=None, smooth=False):
    vm = {v: mb.v(v.co) for v in bm.verts}
    for f in bm.faces:
        idx = [vm[v] for v in f.verts]
        m, uv = mat, None
        if face_mat is not None:
            r = face_mat(f)
            if r is not None:
                m, uvf = r
                uv = [uvf(v.co) for v in f.verts] if uvf else None
        mb.face(idx, m, uv, smooth)


def bbox(mb, c, size, mat, bev=0.003, seg=2, rot=None, face_mat=None, smooth=False):
    """box with bevelled edges (bmesh bevel); rot = Quaternion or 3x3 Matrix; face_mat(face) -> (mat, uv_fn(co)) or None."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    if bev > 0:
        bmesh.ops.bevel(bm, geom=list(bm.edges) + list(bm.verts), offset=min(bev, min(size) * 0.45), segments=seg, affect='EDGES', profile=0.5, clamp_overlap=True)
    R = rot.to_matrix() if isinstance(rot, Quaternion) else (rot if rot is not None else Matrix.Identity(3))
    for v in bm.verts:
        v.co = V(c) + R @ v.co
    bm.normal_update()
    bm_dump(mb, bm, mat, face_mat, smooth or seg >= 2)
    bm.free()


def axes_box(mb, c, xa, ya, za, size, mat, bev=0.003, seg=2, face_mat=None):
    """bevelled box with explicit local axes (unit vectors, right-handed)."""
    xa, ya, za = V(xa).normalized(), V(ya).normalized(), V(za).normalized()
    if xa.cross(ya).dot(za) < 0:          # left-handed axes would mirror the box (inside-out faces): flip z (the box is symmetric)
        za = -za
    R = Matrix((xa, ya, za)).transposed()
    bbox(mb, c, size, mat, bev, seg, R, face_mat)


def wall_x(y, z, inset=0.0):
    """x (>0) of the inner fuselage lining at (y, z)."""
    r = [V((p.x * 0.985, p.y, p.z * 0.985)) for p in fus_ring(y, 144) if p.x >= 0]
    best = min(r, key=lambda p: abs(p.z - z))
    return best.x - inset


def ckart_rect(region):
    """uv fn for a rectangle given as (origin, right axis, up axis, w, h): returns uv of a point."""
    def make(o, ra, ua, w, h):
        def f(p):
            d = V(p) - o
            return L.ckart_uv(region, d.dot(ra) / w + 0.5, d.dot(ua) / h + 0.5)
        return f
    return make


def placard(mb, c, ra, ua, n, w, h, region, off=0.0015, thick=0.0012):
    """thin plate with a ck_art region on its face; c = centre on the mounting surface, n = face normal."""
    ra, ua, n = V(ra).normalized(), V(ua).normalized(), V(n).normalized()
    cc = V(c) + n * (off + thick / 2)
    uvf = ckart_rect(region)(cc + n * thick / 2, ra, ua, w, h)
    def fm(f):
        if f.normal.dot(n) > 0.99:
            return ('ck_art', uvf)
        return None
    R = Matrix((ra, ua, n)).transposed()
    bbox(mb, cc, (w, h, thick), 'ck_alu', bev=0.0004, seg=1, rot=R, face_mat=fm)


# =========================================================================================== instrument parts
def needle_mesh(c, r, kind, zero_deg, n=PN, up0=PU, rt0=X_):
    """needle in its rest pose pointing at the scale's first value; long sword needle with a counterweight tail."""
    a = math.radians(zero_deg)
    up = up0 * math.cos(a) + rt0 * math.sin(a)
    rt = rt0 * math.cos(a) - up0 * math.sin(a)
    nm = MeshBuf()
    if kind == 'ball':
        cc = c - up0 * (r * 0.62)
        disc_face(nm, cc + n * 0.0072, rt0, up0, r * 0.12, 'ball', n, N=12)
        return nm
    Lh = r * (0.86 if kind == 'needle' else 0.58)
    w = 0.0026 if kind == 'needle' else 0.0042
    o = n * (0.0072 if kind == 'needle' else 0.0062)
    tail = r * 0.24
    pts = [c - up * tail - rt * w * 1.6 + o, c - up * tail + rt * w * 1.6 + o, c + rt * w + o, c + up * (0.78 * Lh) + rt * w * 0.75 + o,
           c + up * Lh + o, c + up * (0.78 * Lh) - rt * w * 0.75 + o, c - rt * w + o]
    cell = 'needle' if kind == 'needle' else 'needle'
    uvs = [L.gauge_uv('needle_dark', 0, 0)] * 2 + [L.gauge_uv(cell, 0, 0)] * 5
    vids = [nm.v(p) for p in pts]
    for t in ((0, 1, 2), (0, 2, 6), (6, 2, 3), (6, 3, 5), (5, 3, 4)):
        tri = [vids[k] for k in t]
        P = [nm.verts[k] for k in tri]
        uv = [uvs[k] for k in t]
        if (P[1] - P[0]).cross(P[2] - P[0]).dot(n) < 0:
            tri, uv = [tri[0], tri[2], tri[1]], [uv[0], uv[2], uv[1]]
        nm.face(tri, 'gauges', uv, False)
    disc_face(nm, c + o + n * 0.0010, rt0, up0, 0.0042 if kind == 'needle' else 0.0050, 'hub', n, N=10)
    return nm


def dial(mb, x, h, r, rim, face, base_off, zero=0):
    """bezel ring + recessed face on the panel; returns the face centre."""
    c = pp(x, h, base_off)
    R = r + 0.006
    NS = 32 if r > 0.035 else 24
    rim_mat, rim_uv = ('ck_alu', None) if rim == 'chrome' else ('gauges', L.gauge_uv('rim_' + rim, 0, 0))
    o0 = circle_pts(c + PN * 0.0006, PN, R, NS, ref=PU)
    o1 = circle_pts(c + PN * 0.0085, PN, R, NS, ref=PU)
    o2 = circle_pts(c + PN * 0.0110, PN, R - 0.0018, NS, ref=PU)
    i0 = circle_pts(c + PN * 0.0110, PN, r + 0.0006, NS, ref=PU)
    i1 = circle_pts(c + PN * 0.0040, PN, r + 0.0006, NS, ref=PU)
    strip(mb, o0, o1, rim_mat, rim_uv, outward_of=c)
    strip(mb, o1, o2, rim_mat, rim_uv, outward_of=c - PN * 0.02)
    for a, b in ((o2, i0),):
        n = len(a)
        for j in range(n):
            j1 = (j + 1) % n
            face_o(mb, [a[j], a[j1], b[j1], b[j]], rim_mat, PN, [rim_uv] * 4 if rim_uv else None)
    strip(mb, i0, i1, 'gauges', L.gauge_uv('rim_black', 0, 0), outward_of=c, inward=True)
    disc_face(mb, c + PN * 0.0040, X_, PU, r + 0.0006, face, PN, N=NS)
    return c


def build_panel():
    """cockpit_panel: lower panel, raised centre section, dials, cocks, magneto box, plates, toggles."""
    m = MeshBuf()
    # ---- lower panel plate (front face = ck_art 'lower', edges ck_paint)
    lw = L.LOWER
    outline = L.rounded_rect(lw['x0'], lw['h0'], lw['x1'], lw['h1'], lw['r'])
    plate(m, outline, 0.0, lw['thick'], 'lower')
    # ---- raised centre section
    up_out = L.upper_outline()
    plate(m, up_out, L.UPPER_OFF, L.UPPER_OFF + 0.004, 'upper')
    # 1.4.1: no tubular cross-frame in front of the panel (horizontal tube + two diagonals): not on the real aircraft, and it hid dials
    # and placards (user review 3).
    for s in (-1, 1):   # panel support legs (black tubes) from the lower corners down to the floor
        top = pp(s * 0.300, 0.004, -0.004)
        tube_line(m, [top, V((s * 0.285, top.y + 0.035, -0.20)), V((s * 0.270, top.y + 0.06, S.FLOOR_Z + 0.004))], 0.0095, 'ck_crinkle', N=8)
        bbox(m, V((s * 0.270, top.y + 0.06, S.FLOOR_Z + 0.005)), (0.036, 0.036, 0.008), 'ck_crinkle', bev=0.002, seg=1)
    xc = wall_x(-0.235, -0.20, 0.006)
    tube_line(m, [V((-xc, -0.231, -0.20)), V((xc, -0.231, -0.20))], 0.010, 'ck_tube', N=8)     # cross tube on the fuel-tank bulkhead
    tube_line(m, [V((-0.24, YB - 0.0062, -0.12)), V((-0.10, YB - 0.0062, 0.06)), V((0.12, YB - 0.0062, 0.07)), V((0.30, YB - 0.0062, 0.20))], 0.004, 'ck_brass', N=6)   # fuel / pressure lines behind
    for s in (-1, 1):
        bbox(m, pp(s * (lw['x1'] + 0.012), 0.12, -0.002), (0.034, 0.010, 0.10), 'ck_crinkle', bev=0.002, rot=Matrix((X_, -PN, PU)).transposed())  # side brackets
    # ---- dials
    movers = []
    for gid, d in L.DIALS.items():
        base = L.UPPER_OFF if d.get('upper') else 0.0
        if d.get('plate'):                                       # square mounting plate (boost, photo 50 lower right)
            pw = d['plate']
            bbox(m, pp(d['x'], d['h'], 0.004), (pw, pw, 0.008), 'ck_alu', bev=0.003, rot=Matrix((X_, PU, PN)).transposed())
            base = 0.008
            for sx in (-1, 1):
                for sh in (-1, 1):
                    lathe(m, [(0.0035, 0.0), (0.0035, 0.002), (0.0022, 0.0032)], pp(d['x'] + sx * (pw / 2 - 0.009), d['h'] + sh * (pw / 2 - 0.009), 0.008), PN, 'ck_brass', N=8)
        c = dial(m, d['x'], d['h'], d['r'], d['rim'], d['face'], base, d['zero'])
        if not d['movers']:
            continue
        fr = frame_x(PN, PU)
        movers.append(Part(f'gauge_{gid}', 'cockpit_gauges', c, None, fr, info=dict(kind='gauge', face=d['face'], radius=d['r'])))
        for suf, kind in d['movers']:
            cc = c + (PN * 0.0012 if suf == 'needle' and len(d['movers']) > 1 and d['movers'][1][1] == 'short' else V())
            nm = needle_mesh(cc, d['r'], kind, d['zero'] if kind != 'ball' else 0)
            key = 'slip' if suf == 'slip' else (gid + '_short' if suf == 'needle_short' else gid)
            sc = L.SCALES.get(key, {})
            info = dict(kind='gauge_' + kind, axis_local='+X (Unity) = toward the pilot', rest=f'scale zero at {d["zero"]} deg (clockwise from 12 o\'clock)' if kind != 'ball' else "ball at 6 o'clock",
                        zero_deg=d['zero'] if kind != 'ball' else 0, sign='Unity +angle about local +X = clockwise as seen by the pilot', **sc)
            if 'sweep' in sc:
                info['deg_per_unit'] = round(sc['sweep'] / (sc['v1'] - sc['v0']), 6)
            name = f'gauge_{gid}_{suf}' if suf != 'slip' else 'gauge_slip_needle'
            p = Part(name, f'gauge_{gid}', c, nm, fr, info=info)
            p.own_uv = True
            movers.append(p)
    # ---- tac screen bezel (the screen quad itself is mfd_center)
    t = L.TAC
    bw, bh = t['w'] + 0.022, t['hgt'] + 0.022
    rr = L.rounded_rect(t['x'] - bw / 2, t['h'] - bh / 2, t['x'] + bw / 2, t['h'] + bh / 2, 0.006, 3)
    ri = L.rounded_rect(t['x'] - t['w'] / 2 - 0.001, t['h'] - t['hgt'] / 2 - 0.001, t['x'] + t['w'] / 2 + 0.001, t['h'] + t['hgt'] / 2 + 0.001, 0.002, 3)
    A0 = [pp(x, h, 0.0006) for x, h in rr]; A1 = [pp(x, h, 0.012) for x, h in rr]
    I1 = [pp(x, h, 0.012) for x, h in ri]; I0 = [pp(x, h, 0.0040) for x, h in ri]
    strip(m, A0, A1, 'ck_crinkle', outward_of=pp(t['x'], t['h'], 0.006), smooth=False)
    for j in range(len(A1)):
        j1 = (j + 1) % len(A1)
        face_o(m, [A1[j], A1[j1], I1[j1], I1[j]], 'ck_crinkle', PN)
    strip(m, I1, I0, 'ck_crinkle', outward_of=pp(t['x'], t['h'], 0.006), inward=True, smooth=False)
    face_o(m, I0, 'screen', PN)            # dark back plane behind the screen quad
    for sx in (-1, 1):
        for sh in (-1, 1):
            lathe(m, [(0.0030, 0.0), (0.0030, 0.0015), (0.0018, 0.0026)], pp(t['x'] + sx * (bw / 2 - 0.005), t['h'] + sh * (bh / 2 - 0.005), 0.012), PN, 'ck_alu', N=8)
    # ---- magneto switch box (two toggles)
    mg = L.MAGNETO
    mc = pp(mg['x'], mg['h'], mg['d'] / 2)
    R = Matrix((X_, PU, PN)).transposed()
    uvf = ckart_rect('magneto')(mc + PN * mg['d'] / 2, X_, PU, mg['w'], mg['hgt'])
    bbox(m, mc, (mg['w'], mg['hgt'], mg['d']), 'ck_crinkle', bev=0.003, rot=R, face_mat=lambda f: ('ck_art', uvf) if f.normal.dot(PN) > 0.995 else None)
    for k, sx in enumerate((-0.016, 0.016)):
        toggle(m, pp(mg['x'] + sx, mg['h'] - 0.002, mg['d']), PN, PU, -1 if k == 0 else 1)
    for tx, thh in L.TOGGLES:
        lathe(m, [(0.008, 0.0), (0.008, 0.002), (0.005, 0.006)], pp(tx, thh, 0.0), PN, 'ck_alu', N=12)
        toggle(m, pp(tx, thh, 0.006), PN, PU, 1)
    # ---- brass fuel cocks (body, T-handle, pointer) + brass cock plates
    for cx, ch in L.COCKS:
        c = pp(cx, ch, 0.0)
        lathe(m, [(0.021, 0.0), (0.021, 0.004), (0.017, 0.006), (0.012, 0.010), (0.012, 0.024), (0.009, 0.027)], c, PN, 'ck_brass', N=16)
        hc = c + PN * 0.031
        axes_box(m, hc, X_, PU, PN, (0.052, 0.012, 0.010), 'ck_brass', bev=0.003)
        axes_box(m, hc + PU * 0.012, PU, -X_, PN, (0.018, 0.006, 0.008), 'ck_brass', bev=0.002)   # pointer
    # ---- data plate, card holder, serial label, lower-edge cards
    dp = L.DATAPLATE
    placard(m, pp(dp['x'], dp['h'], 0.0), X_, PU, PN, dp['w'], dp['hgt'], 'dataplate')
    for sx in (-1, 1):
        for sh in (-1, 1):
            lathe(m, [(0.0022, 0.0), (0.0022, 0.0035), (0.0014, 0.0045)], pp(dp['x'] + sx * (dp['w'] / 2 - 0.004), dp['h'] + sh * (dp['hgt'] / 2 - 0.004), 0.0), PN, 'ck_alu', N=6)
    ch_ = L.CARDHOLDER
    sq = L.rounded_rect(ch_['x'] - ch_['w'] / 2, ch_['h'] - ch_['hgt'] / 2, ch_['x'] + ch_['w'] / 2, ch_['h'] + ch_['hgt'] / 2, 0.003, 2)
    sqi = L.rounded_rect(ch_['x'] - ch_['w'] / 2 + 0.006, ch_['h'] - ch_['hgt'] / 2 + 0.006, ch_['x'] + ch_['w'] / 2 - 0.006, ch_['h'] + ch_['hgt'] / 2 - 0.006, 0.002, 2)
    A0 = [pp(x, h, 0.0008) for x, h in sq]; A1 = [pp(x, h, 0.005) for x, h in sq]; I1 = [pp(x, h, 0.005) for x, h in sqi]; I0 = [pp(x, h, 0.0008) for x, h in sqi]
    strip(m, A0, A1, 'ck_crinkle', outward_of=pp(ch_['x'], ch_['h'], 0.003), smooth=False)
    for j in range(len(A1)):
        j1 = (j + 1) % len(A1)
        face_o(m, [A1[j], A1[j1], I1[j1], I1[j]], 'ck_crinkle', PN)
    strip(m, I1, I0, 'ck_crinkle', outward_of=pp(ch_['x'], ch_['h'], 0.003), inward=True, smooth=False)
    sp = L.SERIAL_PLATE
    placard(m, pp(sp['x'], sp['h'], L.UPPER_OFF), X_, PU, PN, sp['w'], sp['hgt'], 'serial')
    for cd in L.LOWER_CARDS:
        placard(m, pp(cd['x'], cd['h'], 0.0), X_, PU, PN, cd['w'], cd['hgt'], cd['id'])
    # ---- panel screws on the upper section corners (the lower panel's screws are painted + normal-mapped)
    for x, h in ((-0.105, 0.215), (0.105, 0.215), (-0.040, 0.445), (0.040, 0.445)):
        lathe(m, [(0.0030, 0.0), (0.0030, 0.0012), (0.0020, 0.0022)], pp(x, h, L.UPPER_OFF), PN, 'ck_alu', N=8)
    return m, movers


def plate(mb, outline, off, thick, region):
    front = [pp(x, h, off) for x, h in outline]
    back = [pp(x, h, off - thick) for x, h in outline]
    for t in ear_clip(outline):
        pts = [front[i] for i in t]
        uv = [L.panel_uv(region, *outline[i]) for i in t]
        face_o(mb, pts, 'ck_art', PN, uv)
    c2 = (sum((p[0] for p in outline)) / len(outline), sum((p[1] for p in outline)) / len(outline))
    n = len(outline)
    for j in range(n):
        j1 = (j + 1) % n
        a, b = outline[j], outline[j1]
        e = V((b[0] - a[0], b[1] - a[1], 0))
        nrm2 = V((e.y, -e.x, 0))          # outward for a CCW outline
        out_dir = X_ * nrm2.x + PU * nrm2.y
        face_o(mb, [front[j], front[j1], back[j1], back[j]], 'ck_paint', out_dir)


def toggle(mb, base, n, up, lean):
    """toggle switch: nut + lever (chrome), leaning up/down."""
    lathe(mb, [(0.0045, 0.0), (0.0045, 0.003)], base, n, 'ck_alu', N=6)
    tip = base + n * 0.016 + up * (0.004 * lean)
    tube_line(mb, [base + n * 0.003, tip], 0.0016, 'ck_alu', N=6)
    lathe(mb, [(0.0026, 0.0), (0.0026, 0.004)], tip - n * 0.001, (tip - base).normalized(), 'ck_alu', N=6)


def build_compass():
    """compass bowl under the lower panel centre (P-type bowl on a bracket): bowl + lubber ring; card is the mover."""
    m = MeshBuf()
    cp = L.COMPASS
    c = V((cp['x'], cp['y'], cp['z']))
    r, hgt = cp['r'], cp['hgt']
    up = V((0, 0, 1))
    lathe(m, [(r * 0.55, -hgt), (r * 0.85, -hgt * 0.92), (r, -hgt * 0.55), (r, -0.006), (r + 0.004, -0.004), (r + 0.004, 0.004)], c, up, 'ck_crinkle', N=28, cap1=False)
    top = circle_pts(c + up * 0.004, up, r + 0.004, 28)
    inner = circle_pts(c + up * 0.004, up, r - 0.006, 28)
    for j in range(28):
        j1 = (j + 1) % 28
        face_o(m, [top[j], top[j1], inner[j1], inner[j]], 'ck_brass', up)
    i2 = circle_pts(c - up * 0.008, up, r - 0.006, 28)
    strip(m, inner, i2, 'gauges', L.gauge_uv('rim_black', 0, 0), outward_of=c, inward=True)
    face_o(m, i2, 'gauges', up, [L.gauge_uv('glass_dark', 0, 0)] * 28)    # bowl floor under the card (dark)
    # lubber line post (forward) and bracket up to the lower panel's bottom edge
    tube_line(m, [c + V((0, r - 0.010, -0.006)), c + V((0, r - 0.010, 0.0035))], 0.0018, 'ck_alu', N=6)
    pb = pp(0, 0.0, -0.002)
    for sx in (-1, 1):
        tube_line(m, [c + V((sx * (r + 0.002), 0.004, -hgt * 0.5)), V((sx * (r + 0.004), pb.y + 0.004, pb.z + 0.006))], 0.0055, 'ck_crinkle', N=8)
        bbox(m, V((sx * (r + 0.004), pb.y + 0.004, pb.z + 0.006)), (0.022, 0.014, 0.018), 'ck_crinkle', bev=0.002)
    card = MeshBuf()
    disc_face(card, c - up * 0.002, X_, V((0, 1, 0)), r - 0.010, 'compass', up, N=28)
    return m, card


def build_breech(side):
    """Vickers Mk III breech casing (cockpit end of the gun), brass feed block, wooden cocking knob on a stalk, crank, chute."""
    m = MeshBuf()
    x = side * S.GUN_X
    y0, y1 = -0.470, -0.300
    z0, z1 = 0.400, 0.512
    c = V((x, (y0 + y1) / 2, (z0 + z1) / 2))
    rear = V((0, -1, 0))
    uvf = ckart_rect('breech')(V((x, y0, (z0 + z1) / 2)), V((1, 0, 0)), V((0, 0, 1)), 0.078, (z1 - z0))
    bbox(m, c, (0.078, y1 - y0, z1 - z0), 'ck_crinkle', bev=0.006, seg=2, face_mat=lambda f: ('ck_art', uvf) if f.normal.dot(rear) > 0.995 else None)
    # top cover ridge + hinge pin, rear crank boss, side plates
    bbox(m, V((x, (y0 + y1) / 2 + 0.01, z1 + 0.004)), (0.050, y1 - y0 - 0.04, 0.010), 'ck_crinkle', bev=0.003)
    tube_line(m, [V((x - 0.028, y1 - 0.025, z1 + 0.003)), V((x + 0.028, y1 - 0.025, z1 + 0.003))], 0.005, 'ck_alu', N=8)
    lathe(m, [(0.016, 0.0), (0.016, 0.006), (0.011, 0.010)], V((x, y0 + 0.0005, (z0 + z1) / 2 - 0.012)), rear, 'ck_crinkle', N=14)
    # crank handle on the right of each gun (Vickers): short lever along the casing side with a knob
    sx = V((side, 0, 0))                     # crank on the outboard side (keeps the raised section clear)
    piv = V((x + side * 0.042, y0 + 0.045, z0 + 0.040))
    lathe(m, [(0.013, 0.0), (0.013, 0.008)], piv - sx * 0.003, sx, 'ck_crinkle', N=12)
    tube_line(m, [piv + sx * 0.009, piv + sx * 0.012 + V((0, 0.050, -0.022))], 0.0055, 'ck_crinkle', N=8)
    lathe(m, [(0.008, 0.0), (0.009, 0.012), (0.007, 0.022)], piv + sx * 0.012 + V((0, 0.050, -0.022)), sx, 'ck_crinkle', N=10)
    # brass feed block on the outboard side (belt from the ammo box below the decking), feed chute down into the wall
    fx = x + side * (0.039 + 0.020)
    fb = V((fx, -0.395, z0 + 0.070))
    bbox(m, fb, (0.040, 0.060, 0.044), 'ck_brass', bev=0.004)
    for dz in (-0.012, 0.012):
        lathe(m, [(0.004, 0.0), (0.004, 0.003)], fb + V((side * 0.020, 0, dz)), V((side, 0, 0)), 'ck_brass', N=6)
    # short belt-guide lip under the feed block (the belt comes up from the ammo box under the decking)
    bbox(m, fb + V((side * 0.006, 0, -0.030)), (0.034, 0.050, 0.018), 'ck_crinkle', bev=0.003)
    # empty-case chute under the casing
    tube_line(m, [V((x, -0.40, z0 + 0.002)), V((x, -0.39, z0 - 0.050)), V((x, -0.37, z0 - 0.085))], 0.012, 'ck_crinkle', N=8, scale=(1.0, 0.6))
    # cocking handle: stalk from the top-outboard rear corner, leaning up and aft, wooden knob
    base = V((x + side * 0.030, y0 + 0.030, z1 + 0.002))
    top = base + V((side * 0.012, -0.022, 0.050))
    lathe(m, [(0.008, 0.0), (0.008, 0.008)], base - V((0, 0, 0.004)), V((0, 0, 1)), 'ck_crinkle', N=10)
    tube_line(m, [base, base + V((side * 0.004, -0.006, 0.024)), top], 0.0042, 'ck_crinkle', N=8)
    d = (top - base).normalized()
    lathe(m, [(0.006, -0.002), (0.0115, 0.008), (0.0130, 0.018), (0.0120, 0.028), (0.0070, 0.036), (0.003, 0.039)], top, d, 'ck_wood', N=12)
    return m


def coaming_round_path():
    """1.8.0: the rounded opening's edge (nimrod_parts.opening_patch), as one closed loop with the inward direction per point."""
    import nimrod_parts as NPm
    if not NPm.OPENING_EDGE:
        NPm.build_fuselage()
    loop = list(NPm.OPENING_EDGE[1]) + list(reversed(NPm.OPENING_EDGE[-1]))
    path = []
    for p in loop:
        if not path or (p - path[-1]).length > 0.008:
            path.append(V(p))
    if len(path) > 2 and (path[0] - path[-1]).length < 0.008:
        path.pop()
    yc = (S.COCKPIT_Y[0] + S.COCKPIT_Y[1]) / 2
    inn = []
    n = len(path)
    for i, p in enumerate(path):
        t = (path[(i + 1) % n] - path[i - 1]); t.z = 0
        t = t.normalized() if t.length > 1e-9 else V((0, 1, 0))
        w = V((-t.y, t.x, 0))
        if w.dot(V((0, yc, p.z)) - p) < 0:
            w = -w
        inn.append(w)
    return path, inn


def build_coaming():
    """slim black leather roll round the opening edge (front arch, sills, rear arch), slightly flattened section."""
    if getattr(S, 'OPENING_ROUND', False):
        path, inn = coaming_round_path()
        return _roll(path, inn, round_open=True)
    y0, y1 = S.COCKPIT_Y[1], S.COCKPIT_Y[0]           # front -0.40, rear -1.05
    sill = S.COCKPIT_SILL_Z
    def arch(y, ccw):
        r = fus_ring(y, 144)
        pts = [p for p in r if p.z >= sill - 1e-6]
        pts.sort(key=lambda p: p.x)
        pts = pts[::4] + [pts[-1]] if len(pts) > 6 else pts
        return pts if ccw else pts[::-1]
    def side_x(y):
        r = [p for p in fus_ring(y, 144) if p.x > 0]
        best = min(r, key=lambda p: abs(p.z - sill))
        return best.x
    fa = arch(y0, True)                 # left -> right along the front edge
    ra = arch(y1, False)                # right -> left along the rear edge
    path, nrm, inn = [], [], []
    for p in fa:
        path.append(V((p.x, y0, p.z))); inn.append(V((0, -1, 0)))
    for k in range(1, 9):
        y = y0 + (y1 - y0) * k / 9
        path.append(V((side_x(y), y, sill))); inn.append(V((-1, 0, 0)))
    for p in ra:
        path.append(V((p.x, y1, p.z))); inn.append(V((0, 1, 0)))
    for k in range(1, 9):
        y = y1 + (y0 - y1) * k / 9
        path.append(V((-side_x(y), y, sill))); inn.append(V((1, 0, 0)))
    return _roll(path, inn)


def _roll(path, inn, round_open=False):
    m = MeshBuf()
    N = 10
    rings = []
    n = len(path)
    for i, p in enumerate(path):
        t = (path[(i + 1) % n] - path[i - 1]).normalized()
        # surface normal: away from the fuselage axis in the section plane (arches), up on the sills
        if round_open:
            sn = V((p.x, 0, p.z)).normalized()          # 1.8.0: the roll sits on the decking round the rounded edge
        elif abs(inn[i].y) > 0.5:
            sn = V((p.x, 0, p.z - 0.0)).normalized()
        else:
            sn = V((0, 0, 1))
        w = (inn[i] - t * inn[i].dot(t)).normalized()
        u = t.cross(w).normalized()
        if u.dot(sn) < 0:
            u = -u
        c = p + u * 0.010 + w * 0.006
        rings.append([c + u * (math.sin(2 * math.pi * k / N) * 0.014) + w * (math.cos(2 * math.pi * k / N) * 0.018) for k in range(N)])
    seq = rings + [rings[0]]
    for i in range(n):
        A, B = seq[i], seq[i + 1]
        mid = (sum(A, V()) + sum(B, V())) / (2 * N)
        for j in range(N):
            j1 = (j + 1) % N
            q = [A[j], A[j1], B[j1], B[j]]
            cq = sum(q, V()) / 4
            nq = (q[1] - q[0]).cross(q[3] - q[0])
            if nq.dot(cq - mid) < 0:
                q = q[::-1]
            m.poly(q, 'ck_leather', None, True)
    # lacing strip under the roll (darker leather band hanging 2 cm into the opening on the sills)
    return m


def build_shell():
    """cockpit_interior: fabric lining, bulkheads, decking underside, footwell, floor."""
    m = MeshBuf()
    sill = S.COCKPIT_SILL_Z
    fz = S.FLOOR_Z
    # one closed lining (doped fabric seen from inside) round the whole bay, only the opening cut out; 0.985 of the skin so the
    # coaming roll covers the seam (1.2.1: eye-ray check found the skin's back faces under the sills and the decking)
    lys = [YA, -1.15, S.COCKPIT_Y[0], -1.0, -0.85, -0.70, -0.55, S.COCKPIT_Y[1], -0.31, YB]
    lrings = [[V((p.x * 0.985, p.y, p.z * 0.985)) for p in fus_ring(y, 72)] for y in lys]
    def keep(i, j):
        a_, b_ = lrings[i][j], lrings[i][(j + 1) % len(lrings[i])]
        a2, b2 = lrings[i + 1][j], lrings[i + 1][(j + 1) % len(lrings[i])]
        if min(a_.z, b_.z, a2.z, b2.z) < fz - 0.06:
            return False
        in_open = S.COCKPIT_Y[0] - 1e-4 <= min(lys[i], lys[i + 1]) and max(lys[i], lys[i + 1]) <= S.COCKPIT_Y[1] + 1e-4
        return not (in_open and (a_.z + b_.z) / 2 >= sill + 0.012)      # up into the coaming roll: no skin seen from inside
    loft(m, lrings, 'ck_lining', outward=False, keep=keep)

    # lips closing the gap between the skin's cut edge and the lining at the front / rear arch of the opening (under the roll)
    for y, toward in ((S.COCKPIT_Y[1], V((0, -1, 0))), (S.COCKPIT_Y[0], V((0, 1, 0)))):
        sk = [p for p in fus_ring(y, 72) if p.z >= sill - 0.02]
        sk.sort(key=lambda p: p.x)
        ln = [V((p.x * 0.985, p.y, p.z * 0.985)) for p in sk]
        for a_, b_, c_, d_ in zip(sk, sk[1:], ln[1:], ln):
            face_o(m, [a_, b_, c_, d_], 'ck_lining', toward)

    def bulk(y, cut, toward):
        ring = [V((p.x * 0.992, y, p.z * 0.992)) for p in fus_ring(y, 72)]      # reaches past the 0.985 lining (no gap at the rim)
        if cut is not None:
            n = len(ring)
            keepi = [k for k in range(n) if ring[k].z >= cut]
            # contiguous arc through the top (index 0): start after the bottom gap
            start = next(k for k in range(n) if ring[k].z >= cut and ring[k - 1].z < cut)
            arc = [ring[(start + k) % n] for k in range(len(keepi))]
            poly2 = [(arc[0].x, cut)] + [(p.x, p.z) for p in arc] + [(arc[-1].x, cut)]
        else:
            poly2 = [(p.x, p.z) for p in ring]
        tris = tessellate_polygon([[V((a, b, 0)) for a, b in poly2]])
        for t in tris:
            face_o(m, [V((poly2[k][0], y, poly2[k][1])) for k in t], 'ck_lining', toward)
    bulk(YB, FOOT_Z, V((0, -1, 0)))
    bulk(YA, None, V((0, 1, 0)))
    # floor (dark red-brown) following the lining, footwell floor / walls / roof
    ys = [YA, -1.15, -1.0, -0.85, -0.70, -0.55, -0.40, YB]
    xs = [wall_x(y, fz + 0.012) - 0.004 for y in ys]
    for (ya, xa), (yb, xb) in zip(zip(ys, xs), zip(ys[1:], xs[1:])):
        face_o(m, [V((-xa, ya, fz)), V((xa, ya, fz)), V((xb, yb, fz)), V((-xb, yb, fz))], 'ck_floor', V((0, 0, 1)))
    wx = 0.26
    face_o(m, [V((-wx, YB, fz)), V((wx, YB, fz)), V((wx, FW_Y, fz)), V((-wx, FW_Y, fz))], 'ck_floor', V((0, 0, 1)))
    for s in (-1, 1):
        face_o(m, [V((s * wx, YB, fz)), V((s * wx, FW_Y, fz)), V((s * wx, FW_Y, FOOT_Z)), V((s * wx, YB, FOOT_Z))], 'ck_lining', V((-s, 0, 0)))
        xl = xs[-1]
        face_o(m, [V((s * wx, YB, fz)), V((s * xl, YB, fz)), V((s * xl, YB, FOOT_Z)), V((s * wx, YB, FOOT_Z))], 'ck_lining', V((0, -1, 0)))
    face_o(m, [V((-wx, FW_Y, fz)), V((wx, FW_Y, fz)), V((wx, FW_Y, FOOT_Z)), V((-wx, FW_Y, FOOT_Z))], 'ck_lining', V((0, -1, 0)))
    face_o(m, [V((-wx, YB, FOOT_Z)), V((wx, YB, FOOT_Z)), V((wx, FW_Y, FOOT_Z)), V((-wx, FW_Y, FOOT_Z))], 'ck_lining', V((0, 0, -1)))
    return m


BREAK_WALL_MAT = 'metal_dark'                   # 2026-11-27 round 2 (review: the interior-paint wall read as a light full-section plate): dark
FOOT_WX = 0.26                                  # footwell half width (build_shell wx)
FOOT_FRONT_Y = None                             # FD-32: -0.068 (fd32 build clips the cockpit lining there; break_walls closes the footwell)


def break_walls(m, wx, fz, gap=0.003, edge=0.002):
    """2026-11-22 (user: "the cockpit is different from the fuselage"; Nimrod / FD-32 break faces opened, r8o pattern): the fuselage
    tank / rear bulkhead discs 60-65 mm inside the y 0 / -1.5 breaks are gone, so the cockpit's own walls (YB front, YA rear, 0.22 m
    from the breaks) are what one sees from a break. They faced the pilot only: here their break-facing sides, `gap` toward the
    break, over the whole fuselage section (outline `edge` inside the skin, past the 2.5 mm inner skin: no slit), the front one with
    the footwell's opening left out; the footwell box gets outward faces. Round 1 drew them in interior paint and the review found
    one uniform light plate over 78-95 % of the section (the rejected 'divider'); round 2: metal_dark (a shadowed cavity end) with
    the longerons, a frame and stringers in front of it (nimrod_parts.cen_stringers). Built into
    fus_center_struct by nimrod_parts.fus_struct (not cockpit_interior: the cockpit's 4 mm tuck would open a slit at the inner skin)."""
    from nimrod_structure import fus_params
    for y, toward, hole in ((YB + gap, V((0, 1, 0)), True), (YA - gap, V((0, -1, 0)), False)):
        hw, zt, zb, n_ = fus_params(y)
        c = V((0, y, (zt + zb) / 2))
        ring = [V((p.x, y, p.z)) for p in fus_ring(y, 72)]
        ring = [p + (c - p).normalized() * edge for p in ring]
        loops = [ring]
        if hole:
            loops.append([V((-wx - 0.002, y, fz - 0.002)), V((wx + 0.002, y, fz - 0.002)), V((wx + 0.002, y, FOOT_Z + 0.002)),
                          V((-wx - 0.002, y, FOOT_Z + 0.002))])
        flat = [[V((p.x, p.z, 0.0)) for p in lp] for lp in loops]
        allp = [p for lp in loops for p in lp]
        for t in tessellate_polygon(flat):
            face_o(m, [allp[k] for k in t], BREAK_WALL_MAT, toward)
    # footwell box (YB .. FW_Y, |x| < wx, fz .. FOOT_Z): outward faces 2 mm outside its lining faces
    o = 0.002
    fw = FW_Y if FOOT_FRONT_Y is None else FOOT_FRONT_Y
    yb_, yf_ = YB + gap, fw + o
    # the front wall's cut edge (FOOT_Z) can sit up to 1 mm over the footwell roof after the cockpit tuck: a 2.5 mm cockpit-side strip
    # closes the slab between the roof lining and its outward twin there (seen from the cockpit through that slit: a back face)
    face_o(m, [V((-wx - o, YB - 0.0005, FOOT_Z - 0.001)), V((wx + o, YB - 0.0005, FOOT_Z - 0.001)), V((wx + o, YB - 0.0005, FOOT_Z + 0.0015)),
               V((-wx - o, YB - 0.0005, FOOT_Z + 0.0015))], 'ck_lining', V((0, -1, 0)))
    if FOOT_FRONT_Y is not None:        # FD-32: its builder clips the cockpit lining at y -0.068 (the footwell front wall went with it)
        face_o(m, [V((-wx, fw, fz)), V((wx, fw, fz)), V((wx, fw, FOOT_Z)), V((-wx, fw, FOOT_Z))], 'ck_lining', V((0, -1, 0)))
    for s in (-1, 1):
        face_o(m, [V((s * (wx + o), yb_, fz - o)), V((s * (wx + o), yf_, fz - o)), V((s * (wx + o), yf_, FOOT_Z + o)),
                   V((s * (wx + o), yb_, FOOT_Z + o))], BREAK_WALL_MAT, V((s, 0, 0)))
    face_o(m, [V((-wx - o, yf_, fz - o)), V((wx + o, yf_, fz - o)), V((wx + o, yf_, FOOT_Z + o)), V((-wx - o, yf_, FOOT_Z + o))],
           BREAK_WALL_MAT, V((0, 1, 0)))
    face_o(m, [V((-wx - o, yb_, FOOT_Z + o)), V((wx + o, yb_, FOOT_Z + o)), V((wx + o, yf_, FOOT_Z + o)), V((-wx - o, yf_, FOOT_Z + o))],
           BREAK_WALL_MAT, V((0, 0, 1)))
    face_o(m, [V((-wx - o, yb_, fz - o)), V((wx + o, yb_, fz - o)), V((wx + o, yf_, fz - o)), V((-wx - o, yf_, fz - o))],
           BREAK_WALL_MAT, V((0, 0, -1)))


FRAME_Y = [-1.20, -0.78, -0.36]
FRAME_ZT, FRAME_ZB = 0.455, -0.455


def build_frames():
    """cockpit_frame: steel-tube side frames (longerons, verticals, diagonal bracing tubes, gussets), cross tubes under the floor,
    one wire-braced bay (right rear) with a turnbuckle."""
    m = MeshBuf()
    zt, zb = FRAME_ZT, FRAME_ZB
    for s in (-1, 1):
        def P(y, z, r=0.013):
            return V((s * wall_x(y, z, r + 0.008), y, z))
        for z in (zt, zb):
            tube_line(m, [P(y, z) for y in (YA + 0.01, -1.20, -0.99, -0.78, -0.57, -0.36, YB - 0.004)], 0.013, 'ck_tube', N=10)
        for y in FRAME_Y:
            tube_line(m, [P(y, z, 0.011) for z in (zb, -0.25, 0.0, 0.25, zt)], 0.011, 'ck_tube', N=10)
        for ya, yb in ((-1.20, -0.78), (-0.78, -0.36)):
            tube_line(m, [P(ya, zb, 0.0095), P((ya + yb) / 2, 0.0, 0.0095), P(yb, zt, 0.0095)], 0.0095, 'ck_tube', N=8)
        if s > 0:   # bracing wire across the right rear bay
            a, b = P(-1.20, zt, 0.004), P(-0.78, zb, 0.004)
            tube_line(m, [a, b], 0.0022, 'ck_alu', N=5, cap=False)
            mid = a.lerp(b, 0.62)
            lathe(m, [(0.0040, -0.022), (0.0052, -0.012), (0.0052, 0.012), (0.0040, 0.022)], mid, (b - a).normalized(), 'ck_brass', N=8)
        for y in FRAME_Y:     # gusset plates at the joints
            for z in (zt, zb):
                c = P(y, z, 0.0)
                bbox(m, c + V((-s * 0.006, 0, 0)), (0.004, 0.060, 0.060), 'ck_tube', bev=0.001, seg=1)
    for y in (-1.20, -0.36):          # cross tubes under the floor
        x = wall_x(y, zb, 0.015)
        tube_line(m, [V((-x, y, S.FLOOR_Z - 0.016)), V((x, y, S.FLOOR_Z - 0.016))], 0.011, 'ck_tube', N=8)
    return m


def build_floor():
    """cockpit_floor: wooden footboards with cleats, heel plates, column torque tube with bearings, rudder-bar pivot post."""
    m = MeshBuf()
    fz = S.FLOOR_Z
    for s in (-1, 1):
        x = s * 0.168
        y0, y1 = -0.66, -0.14
        L_ = y1 - y0
        bbox(m, V((x, (y0 + y1) / 2, fz + 0.0015 + 0.008)), (0.125, L_, 0.016), 'ck_wood', bev=0.003, seg=1)
        for k in range(6):
            y = y0 + 0.05 + k * (L_ - 0.10) / 5
            bbox(m, V((x, y, fz + 0.0175 + 0.004)), (0.118, 0.014, 0.008), 'ck_crinkle', bev=0.002, seg=1)
        bbox(m, V((x, y0 + 0.07, fz + 0.0195 + 0.0008)), (0.10, 0.11, 0.004), 'ck_alu', bev=0.001, seg=1)        # heel plate
        bbox(m, V((x, y1 - 0.01, fz + 0.034)), (0.125, 0.020, 0.036), 'ck_wood', bev=0.003, seg=1)     # toe stop
    # column torque tube (fore-aft) with two bearing blocks, elevator cable quadrant
    tz = fz + 0.030
    tube_line(m, [V((0, -0.80, tz)), V((0, -0.30, tz))], 0.018, 'ck_tube', N=12)
    for y in (-0.78, -0.33):
        bbox(m, V((0, y, fz + 0.017)), (0.060, 0.040, 0.032), 'ck_crinkle', bev=0.004)
        lathe(m, [(0.024, -0.02), (0.024, 0.02)], V((0, y, tz)), V((0, 1, 0)), 'ck_crinkle', N=12)
    # elevator / aileron cables along the floor (from the column base aft and forward)
    for s in (-1, 1):
        tube_line(m, [V((s * 0.012, -0.70, tz)), V((s * 0.045, -0.80, fz + 0.004)), V((s * 0.050, YA + 0.004, fz + 0.004))], 0.0018, 'ck_alu', N=5, cap=False)
        tube_line(m, [V((s * 0.012, -0.40, tz)), V((s * 0.050, -0.28, fz + 0.004)), V((s * 0.080, FW_Y - 0.004, fz + 0.004))], 0.0018, 'ck_alu', N=5, cap=False)
    # 1.4.0 (user review 2): the rudder bar and its pivot post are removed ('remove the pedals from all three aircraft'); the floor is
    # whole under them (footboards + floor shell), nothing else changes
    if RUDDER_BAR:
        rp = RUDDER_PIVOT
        lathe(m, [(0.032, 0.001), (0.032, 0.008), (0.020, 0.014), (0.020, rp.z - fz - 0.012)], V((rp.x, rp.y, fz)), V((0, 0, 1)), 'ck_crinkle', N=14)
    return m


RUDDER_BAR = False


RUDDER_PIVOT = V((0, -0.205, S.FLOOR_Z + 0.055))


def build_rudderbar():
    """2026-11-02 rebuild (user review 1: 'rudder pedals not at all correct'): the fal 3D rudder bar (concept from the reference
    photos refs/nimrod_cockpit_user 51-55: steel tube bar on a centre bearing, a foot plate with a chromed toe stirrup at each end;
    fal-ai/nano-banana-2 -> tripo3d/h3.1 -> tripo remesh, nimrod_props). Its own floor post is replaced by a pivot post on the yaw
    axis through RUDDER_PIVOT (ControlSurface turns the whole object about local X = up). The bar sits 7 cm ahead of / 5 cm above
    the pivot so the plates are under the pilot figure's feet; plates tilted 40 deg to face aft and up."""
    import nimrod_props as PR
    rb = MeshBuf()
    rp = RUDDER_PIVOT
    a = math.radians(40)
    s_ = 0.47
    xm = V((0, math.cos(a), math.sin(a)))          # model +x (plate length) -> forward-up
    zm = V((0, -math.sin(a), math.cos(a)))         # model +z (plate normal) -> aft-up
    R = PR.axes(xm, V((1, 0, 0)), zm, s_, s_, s_)
    if R.determinant() < 0:
        R = PR.axes(-xm, V((1, 0, 0)), zm, s_, s_, s_)
    bar = rp + V((0, 0.07, 0.05))
    am = V((0.032, 0.0, 0.032))
    PR.place(rb, 'pedals_lp', R, am, bar, keep=lambda vs: not all(abs(v[1]) < 0.13 and v[2] < -0.012 for v in vs))
    # the low-poly fal remesh (tripo face_limit 500, which keeps the stirrup loops) dropped the bar between the hub and the pedal
    # arms: the bar itself is a plain steel tube on the hub axis (fit geometry)
    tube_line(rb, [bar + R @ (V((0.032, -0.33, 0.032)) - am), bar + R @ (V((0.032, 0.33, 0.032)) - am)], 0.0062, 'ck_tube', N=10)
    lathe(rb, [(0.026, -0.012), (0.026, 0.020)], rp - V((0, 0, 0.005)), V((0, 0, 1)), 'ck_crinkle', N=14)          # floor bearing
    tube_line(rb, [rp, rp + V((0, 0, 0.05)), bar + V((0, 0, -0.012))], 0.013, 'ck_crinkle', N=10)                   # pivot post + arm
    return rb


def build_stick():
    """spade-grip control column: black tube from the torque tube, ring grip wrapped in black rubber cord, gun lever."""
    st = MeshBuf()
    cp = STICK_PIVOT
    top = cp + V((0, 0.035, 0.520))
    lathe(st, [(0.030, -0.015), (0.030, 0.035)], cp, V((0, 1, 0)), 'ck_crinkle', N=12)       # hub on the torque tube
    tube_line(st, [cp + V((0, 0, 0.02)), cp + V((0, 0.010, 0.25)), top], 0.0155, 'ck_tube', N=12)
    lathe(st, [(0.020, 0.0), (0.020, 0.030), (0.016, 0.040)], cp + V((0, 0.004, 0.10)), (top - cp).normalized(), 'ck_rubber', N=12)   # gaiter
    gc = top + V((0, 0.0, 0.088))
    ring = [gc + V((math.cos(2 * math.pi * k / 36) * 0.086, 0, math.sin(2 * math.pi * k / 36) * 0.086)) for k in range(36)]
    tube_line(st, ring, 0.0125, 'ck_rubber', N=10, closed=True)
    right, left, bottom = ring[0], ring[18], ring[27]
    for side_pt, s in ((right, 1), (left, -1)):
        tube_line(st, [top + V((s * 0.004, 0, 0.0)), top + V((s * 0.034, 0, 0.018)), side_pt - V((s * 0.006, 0, 0))], 0.0085, 'ck_tube', N=8)
    lathe(st, [(0.018, 0.0), (0.018, 0.022)], top - V((0, 0, 0.012)), V((0, 0, 1)), 'ck_crinkle', N=12)
    # gun-firing lever and button block (silver) at the bottom of the ring (photo 50)
    bc = bottom + V((0, -0.016, 0.004))
    axes_box(st, bc, X_, V((0, 0, 1)), V((0, -1, 0)), (0.040, 0.028, 0.018), 'ck_alu', bev=0.004)
    for sx in (-1, 1):
        lathe(st, [(0.0065, 0.0), (0.0065, 0.010), (0.004, 0.014)], bc + V((sx * 0.010, -0.008, 0.006)), V((0, -0.5, 0.86)), 'ck_alu', N=10)
    tube_line(st, [bottom + V((0, -0.012, -0.004)), bottom + V((0, -0.050, 0.010)), bottom + V((0, -0.066, 0.040))], 0.0035, 'ck_alu', N=6)
    return st


STICK_PIVOT = V((0, -0.62, S.FLOOR_Z + 0.030))


def build_seat():
    """riveted aluminium bucket seat (ck_art 'seat' skin with painted rivet rows), rolled rim, mounting tubes, Sutton harness."""
    m = MeshBuf()
    hw = 0.215
    path = [(-0.700, -0.155), (-0.760, -0.172), (-0.880, -0.178), (-1.000, -0.172), (-1.075, -0.140), (-1.105, -0.060), (-1.130, 0.060),
            (-1.155, 0.180), (-1.175, 0.290)]
    side_h = [0.090, 0.110, 0.120, 0.130, 0.140, 0.140, 0.130, 0.110, 0.080]
    inside = V((0, -0.93, 0.05))
    sl = [0.0]
    for (ya, za), (yb, zb) in zip(path, path[1:]):
        sl.append(sl[-1] + math.hypot(yb - ya, zb - za))
    rings_o, rings_i = [], []
    for i, (y, z) in enumerate(path):
        a = path[max(i - 1, 0)]; b = path[min(i + 1, len(path) - 1)]
        t = V((0, b[0] - a[0], b[1] - a[1])).normalized()
        nn = V((0, -t.z, t.y))
        c = V((0, y, z))
        if nn.dot(inside - c) < 0:
            nn = -nn
        hh = side_h[i]
        prof = [(-hw, hh), (-hw, 0.030), (-hw + 0.010, 0.008), (-hw + 0.030, 0.0), (hw - 0.030, 0.0), (hw - 0.010, 0.008), (hw, 0.030), (hw, hh)]
        # side walls rise straight up along the pan and turn with the back only above the bend (no folded quads at the bend)
        tw = 0.0 if i <= 4 else (0.5 if i == 5 else 1.0)
        wdir = (V((0, 0, 1)) * (1 - tw) + nn * tw).normalized()
        def P(px, pz, off):
            if pz <= 0.030:
                return c + X_ * px + nn * (pz + off)
            return c + X_ * px + nn * (0.030 + off) + wdir * (pz - 0.030)
        rings_o.append([P(px, pz, 0.0) for px, pz in prof])
        rings_i.append([P(px * (1 - 0.003 / hw), pz, 0.003) for px, pz in prof])
    pr = [(-hw, 0.12), (-hw, 0.030), (-hw + 0.010, 0.008), (-hw + 0.030, 0.0), (hw - 0.030, 0.0), (hw - 0.010, 0.008), (hw, 0.030), (hw, 0.12)]
    ua = [0.0]
    for (xa, za), (xb, zb) in zip(pr, pr[1:]):
        ua.append(ua[-1] + math.hypot(xb - xa, zb - za))
    UT, VT = ua[-1], sl[-1]
    nP = len(pr)
    for i in range(len(path) - 1):
        for j in range(nP - 1):
            for rings, flip, mat in ((rings_i, False, 'ck_art'), (rings_o, True, 'ck_alu')):
                q = [rings[i][j], rings[i][j + 1], rings[i + 1][j + 1], rings[i + 1][j]]
                uv = [L.ckart_uv('seat', ua[jj] / UT, 1 - sl[ii] / VT) for ii, jj in ((i, j), (i, j + 1), (i + 1, j + 1), (i + 1, j))]
                cq = sum(q, V()) / 4
                nq = (q[1] - q[0]).cross(q[3] - q[0])
                want = (inside - cq) * (-1 if flip else 1)
                if nq.dot(want) < 0:
                    q = q[::-1]; uv = uv[::-1]
                m.poly(q, mat, uv if mat == 'ck_art' else None, True)
    for s in (0, nP - 1):
        tube_line(m, [(rings_o[i][s] + rings_i[i][s]) / 2 for i in range(len(path))], 0.0055, 'ck_alu', N=8)
    tube_line(m, [(rings_o[-1][j] + rings_i[-1][j]) / 2 for j in range(nP)], 0.0055, 'ck_alu', N=8)
    tube_line(m, [(rings_o[0][j] + rings_i[0][j]) / 2 for j in range(nP)], 0.0055, 'ck_alu', N=8)
    # parachute pack / cushion in the pan (dark leather)
    bbox(m, V((0, -0.885, -0.178 + 0.003 + 0.036)), (0.36, 0.30, 0.072), 'ck_leather', bev=0.022, seg=3)
    for s in (-1, 1):
        for y in (-0.76, -1.02):
            tube_line(m, [V((s * 0.150, y, S.FLOOR_Z + 0.002)), V((s * 0.150, y, -0.172 - 0.004))], 0.012, 'ck_tube', N=8)
            bbox(m, V((s * 0.150, y, S.FLOOR_Z + 0.006)), (0.040, 0.040, 0.010), 'ck_crinkle', bev=0.002, seg=1)
        tube_line(m, [V((s * (hw - 0.002), -1.13, 0.10)), V((s * (wall_x(-1.20, 0.10) - 0.026), -1.20, 0.10))], 0.009, 'ck_tube', N=8)
        tube_line(m, [V((s * 0.12, -1.093, -0.10)), V((s * 0.20, -1.20, S.FLOOR_Z + 0.04))], 0.009, 'ck_tube', N=8)

    def strap(pts, w):
        P = [V(p) for p in pts]
        for a, b in zip(P, P[1:]):
            d = (b - a).normalized()
            side = d.cross(V((0, 1, 0)) if abs(d.y) < 0.9 else V((0, 0, 1))).normalized() * (w / 2)
            q = [a - side, a + side, b + side, b - side]
            nrm = (q[1] - q[0]).cross(q[3] - q[0]).normalized()
            if nrm.dot(V(S.EYE) - a) < 0:     # top face toward the pilot's eye, back face 1.2 mm behind it
                nrm = -nrm
            face_o(m, q, 'ck_canvas', nrm)
            face_o(m, [p - nrm * 0.0012 for p in q], 'ck_canvas', -nrm)
    for s in (-1, 1):
        x = s * 0.060
        strap([V((x, -1.205, 0.24)), V((x, -1.186, 0.298)), V((x * 1.05, -1.170, 0.272)), V((x * 1.1, -1.150, 0.16)), V((x * 1.2, -1.127, 0.05)),
               V((x * 1.3, -1.104, -0.03))], 0.046)
        strap([V((s * 0.186, -1.02, -0.150)), V((s * 0.168, -0.97, -0.099)), V((s * 0.150, -0.86, -0.101))], 0.040)
        axes_box(m, V((x * 1.12, -1.137, 0.13)), X_, V((0, -0.19, 0.98)), V((0, 0.98, 0.19)), (0.054, 0.030, 0.004), 'ck_alu', bev=0.001, seg=1)
    axes_box(m, V((0, -0.86, -0.099)), X_, V((0, 1, 0)), V((0, 0, 1)), (0.070, 0.050, 0.006), 'ck_alu', bev=0.002, seg=1)   # pin plate
    return m


QUAD_PIVOT = V((-0.335, -0.600, 0.160))
QUAD_COLS = [(-0.028, -0.022, 'side'), (-0.010, -0.002, 'bar'), (0.010, 0.016, 'side')]   # slots: mixture -0.022..-0.010, throttle -0.002..0.010
THROTTLE_X = QUAD_PIVOT.x + 0.004
MIXTURE_X = QUAD_PIVOT.x - 0.016


def build_quadrant():
    """left-wall throttle quadrant: alu sector housing, two 12 mm slots (mixture outboard, throttle inboard), mixture lever."""
    m = MeshBuf()
    P = QUAD_PIVOT
    R = 0.100
    a0, a1 = -42, 42
    def arcp(r, x):
        return [P + V((x, math.sin(math.radians(a)) * r, math.cos(math.radians(a)) * r)) for a in range(a0, a1 + 1, 6)]
    zb = P.z - 0.030
    for x0, x1, kind in QUAD_COLS:
        top0, top1 = arcp(R, x0), arcp(R, x1)
        n = len(top0)
        inner_r = 0.0 if kind == 'side' else R - 0.008
        if kind == 'side':
            for xx, toward in ((x0, V((-1, 0, 0))), (x1, V((1, 0, 0)))):
                arcpts = arcp(R, xx)
                poly = [V((P.x + xx, arcpts[0].y, zb))] + arcpts + [V((P.x + xx, arcpts[-1].y, zb))]
                for t in tessellate_polygon([[V((p.y, p.z, 0)) for p in poly]]):
                    face_o(m, [poly[k] for k in t], 'ck_alu', toward)
            for j in range(n - 1):
                face_o(m, [top0[j], top1[j], top1[j + 1], top0[j + 1]], 'ck_alu', (top0[j] - P - X_ * x0).normalized())
            for e, d in ((0, -1), (n - 1, 1)):
                a, b = top0[e], top1[e]
                face_o(m, [a, b, V((b.x, b.y, zb)), V((a.x, a.y, zb))], 'ck_alu', V((0, d, 0)))
        else:
            in0, in1 = arcp(R - 0.008, x0), arcp(R - 0.008, x1)
            for j in range(n - 1):
                face_o(m, [top0[j], top1[j], top1[j + 1], top0[j + 1]], 'ck_alu', (top0[j] - P - X_ * x0).normalized())
                face_o(m, [top0[j], top0[j + 1], in0[j + 1], in0[j]], 'ck_alu', V((-1, 0, 0)))
                face_o(m, [top1[j], top1[j + 1], in1[j + 1], in1[j]], 'ck_alu', V((1, 0, 0)))
                face_o(m, [in0[j], in1[j], in1[j + 1], in0[j + 1]], 'ck_crinkle', (P + X_ * x0 - in0[j]).normalized())
            for e, d in ((0, -1), (n - 1, 1)):
                face_o(m, [top0[e], top1[e], in1[e], in0[e]], 'ck_alu', V((0, d, 0)))
    # black base and wall bracket
    bbox(m, V((P.x - 0.006, P.y, zb - 0.015)), (0.060, 0.150, 0.030), 'ck_crinkle', bev=0.004)
    wx = wall_x(P.y, zb - 0.015, 0.0)
    bx0, bx1 = -wx + 0.002, P.x - 0.034
    bbox(m, V(((bx0 + bx1) / 2, P.y, zb - 0.015)), (bx1 - bx0 + 0.004, 0.090, 0.024), 'ck_crinkle', bev=0.003)
    # pivot bosses outside the slots + friction knob (inboard)
    lathe(m, [(0.012, -0.040), (0.012, -0.022)], P, X_, 'ck_crinkle', N=14)
    lathe(m, [(0.012, 0.010), (0.012, 0.030)], P, X_, 'ck_crinkle', N=14)
    lathe(m, [(0.020, 0.030), (0.020, 0.038), (0.013, 0.044)], P, X_, 'ck_alu', N=14)
    # mixture lever (static, outboard slot), red knob
    ang = math.radians(-12)
    d = V((0, math.sin(ang), math.cos(ang)))
    mp = V((MIXTURE_X, P.y, P.z))
    lathe(m, [(0.010, -0.0035), (0.010, 0.0035)], mp, X_, 'ck_alu', N=12)
    tube_line(m, [mp, mp + d * 0.165], 0.0038, 'ck_alu', N=8)
    lathe(m, [(0.006, 0.0), (0.011, 0.008), (0.012, 0.020), (0.008, 0.030)], mp + d * 0.160, d, 'ck_red', N=12)
    # engraved quadrant plate on the wall above
    wx2 = wall_x(P.y, P.z + 0.075, 0.0)
    placard(m, V((-wx2, P.y, P.z + 0.075)), V((0, 1, 0)), V((0, 0, 1)), V((1, 0, 0)), 0.150, 0.038, 'quadrant', off=0.003)
    return m


def build_throttle():
    th = MeshBuf()
    piv = V((THROTTLE_X, QUAD_PIVOT.y, QUAD_PIVOT.z))
    lean = math.radians(-22)                                                    # idle: top leaning aft; +40 deg swings it forward
    d = V((0, math.sin(lean), math.cos(lean)))
    lathe(th, [(0.0105, -0.0040), (0.0105, 0.0040)], piv, X_, 'ck_alu', N=12)
    tube_line(th, [piv, piv + d * 0.175], 0.0040, 'ck_alu', N=8)
    tip = piv + d * 0.170
    lathe(th, [(0.007, 0.0), (0.016, 0.010), (0.019, 0.025), (0.017, 0.040), (0.008, 0.050)], tip, d, 'ck_crinkle', N=14)
    return th


def build_trimwheel():
    """large red-orange elevator trim wheel on the left wall: web with six round holes, rim, black hub, wall bracket, indicator."""
    m = MeshBuf()
    c = TRIM_C
    ax = V((1, 0, 0))
    R, Ri, Rh, t = 0.108, 0.094, 0.026, 0.010
    ref = V((0, 0, 1))
    lathe(m, [(Ri, -0.009), (R - 0.004, -0.0095), (R, -0.005), (R, 0.005), (R - 0.004, 0.0095), (Ri, 0.009)], c, ax, 'ck_red', N=48, ref=ref, cap0=False, cap1=False)
    iw0, iw1 = circle_pts(c - ax * 0.009, ax, Ri, 48, ref), circle_pts(c + ax * 0.009, ax, Ri, 48, ref)
    strip(m, iw0, iw1, 'ck_red', outward_of=c, inward=True)
    e1 = V((0, 1, 0)); e2 = V((0, 0, 1))
    outer = [(math.cos(2 * math.pi * k / 48) * (Ri + 0.001), math.sin(2 * math.pi * k / 48) * (Ri + 0.001)) for k in range(48)]
    holes = []
    for h in range(6):
        a = 2 * math.pi * h / 6 + math.pi / 6
        hc = (math.cos(a) * 0.060, math.sin(a) * 0.060)
        holes.append([(hc[0] + math.cos(2 * math.pi * k / 14) * 0.020, hc[1] + math.sin(2 * math.pi * k / 14) * 0.020) for k in range(14)])
    hub = [(math.cos(2 * math.pi * k / 20) * Rh, math.sin(2 * math.pi * k / 20) * Rh) for k in range(20)]
    loops = [outer] + holes + [hub]
    flat = [p for lp in loops for p in lp]
    tris = tessellate_polygon([[V((a, b, 0)) for a, b in lp] for lp in loops])
    for side in (-1, 1):
        cc = c + ax * (side * t / 2)
        for tr in tris:
            face_o(m, [cc + e1 * flat[k][0] + e2 * flat[k][1] for k in tr], 'ck_red', ax * side)
    for hl in holes:
        A = [c - ax * t / 2 + e1 * x + e2 * y for x, y in hl]
        B = [c + ax * t / 2 + e1 * x + e2 * y for x, y in hl]
        strip(m, A, B, 'ck_red', outward_of=sum(A, V()) / len(A), inward=True)
    lathe(m, [(Rh, -0.016), (Rh, 0.016)], c, ax, 'ck_crinkle', N=20, ref=ref)
    lathe(m, [(0.012, 0.016), (0.012, 0.024)], c, ax, 'ck_alu', N=6, ref=ref)
    wx = wall_x(c.y, c.z, 0.0)
    tube_line(m, [c - ax * 0.016, V((-wx + 0.012, c.y, c.z))], 0.009, 'ck_crinkle', N=10)
    bbox(m, V((-wx + 0.010, c.y, c.z)), (0.014, 0.060, 0.120), 'ck_crinkle', bev=0.003)
    # trim indicator card on the wall aft of / above the wheel
    y, z = -0.95, 0.26
    wx2 = wall_x(y, z, 0.0)
    placard(m, V((-wx2, y, z)), V((0, 1, 0)), V((0, 0, 1)), V((1, 0, 0)), 0.064, 0.032, 'trimcard', off=0.003)
    return m


TRIM_C = V((-0.330, -0.880, 0.020))


def build_wall_left():
    m = MeshBuf()
    # two T pull handles with Bowden cables near the panel (slow-running cut-out, flare release)
    for k, (y, z) in enumerate(((-0.40, 0.255), (-0.40, 0.190))):
        wx = wall_x(y, z, 0.0)
        bb = V((-wx + 0.012, y, z))
        bbox(m, bb, (0.024, 0.036, 0.026), 'ck_crinkle', bev=0.003)
        tube_line(m, [bb + V((0.012, 0, 0)), bb + V((0.045, 0, 0))], 0.0035, 'ck_alu', N=6)
        tube_line(m, [bb + V((0.045, 0, -0.016)), bb + V((0.045, 0, 0.016))], 0.0055, 'ck_crinkle' if k else 'ck_red', N=8)
        cab = [bb + V((-0.006, -0.018, 0)), V((-wx + 0.008, y - 0.10, z - 0.10)), V((-wx + 0.008, -0.60, -0.10)), V((-wx + 0.008, -0.95, -0.20)), V((-wx + 0.008, YA + 0.004, -0.22))]
        tube_line(m, cab, 0.0035, 'ck_rubber', N=6)
    # throttle / mixture rods from the quadrant base outboard to the wall and forward to the bulkhead
    for k, dz in enumerate((-0.050, -0.064)):
        x0 = QUAD_PIVOT.x - 0.034
        xw = -wall_x(-0.60, QUAD_PIVOT.z + dz, 0.0) + 0.030
        tube_line(m, [V((x0, -0.62 + 0.03 * k, QUAD_PIVOT.z + dz)), V((xw, -0.58 + 0.03 * k, QUAD_PIVOT.z + dz)), V((xw, YB - 0.004, QUAD_PIVOT.z + dz))], 0.0045, 'ck_tube', N=6)
    # small valve hand-wheel (radiator shutter) low forward
    y, z = -0.47, 0.030
    vc = V((-wall_x(y, z, 0.0) + 0.040, y, z))
    ring = circle_pts(vc, X_, 0.032, 20)
    tube_line(m, ring, 0.0045, 'ck_crinkle', N=6, closed=True)
    for k in range(3):
        tube_line(m, [vc, ring[k * 7]], 0.003, 'ck_crinkle', N=5)
    tube_line(m, [vc, vc - V((0.030, 0, 0))], 0.006, 'ck_brass', N=8)
    bbox(m, vc - V((0.030, 0, 0)), (0.012, 0.040, 0.040), 'ck_brass', bev=0.003)
    # wall data card (engine limits) aft, low beside the seat; map case
    y, z = -1.10, -0.05
    wx = wall_x(y, z, 0.0)
    placard(m, V((-wx, y, z)), V((0, 1, 0)), V((0, 0, 1)), V((1, 0, 0)), 0.090, 0.045, 'wallcard2', off=0.003)
    y, z = -1.05, 0.13
    wx = wall_x(y, z, 0.0)
    bbox(m, V((-wx + 0.026, y, z)), (0.052, 0.14, 0.09), 'ck_crinkle', bev=0.005)
    return m


def build_wall_right():
    m = MeshBuf()
    # gun-firing / ammo-counter box (face = ck_art 'ammo') near the panel, upper right
    y, z = -0.55, 0.33
    wx = wall_x(y, z, 0.0)
    bc = V((wx - 0.026, y, z))
    uvf = ckart_rect('ammo')(bc + V((-0.026, 0, 0)), V((0, -1, 0)), V((0, 0, 1)), 0.110, 0.074)
    bbox(m, bc, (0.052, 0.110, 0.074), 'ck_crinkle', bev=0.004, face_mat=lambda f: ('ck_art', uvf) if f.normal.x < -0.995 else None)
    for dz in (-0.022, 0.022):
        toggle(m, bc + V((-0.026, 0.040, dz)), V((-1, 0, 0)), V((0, 0, 1)), 1)
    tube_line(m, [bc + V((0.010, 0.056, -0.020)), V((wx - 0.012, -0.40, 0.30)), V((wx - 0.012, YB - 0.004, 0.27))], 0.0045, 'ck_rubber', N=6)
    # priming pump (Ki-gass type): brass barrel on wall clips, plunger with a T handle, label plate
    y, z = -0.44, 0.10
    wx = wall_x(y, z, 0.0)
    pc = V((wx - 0.034, y, z))
    lathe(m, [(0.017, -0.070), (0.019, -0.064), (0.019, 0.040), (0.016, 0.046), (0.007, 0.050)], pc, V((0, 0, 1)), 'ck_brass', N=16)
    tube_line(m, [pc + V((0, 0, 0.050)), pc + V((0, 0, 0.072))], 0.0045, 'ck_alu', N=8)
    axes_box(m, pc + V((0, 0, 0.078)), V((0, 1, 0)), V((1, 0, 0)), V((0, 0, 1)), (0.050, 0.014, 0.014), 'ck_brass', bev=0.004)
    for dz in (-0.040, 0.025):
        bbox(m, V((wx - 0.010, y, z + dz)), (0.030, 0.026, 0.012), 'ck_crinkle', bev=0.002)
    wxp = wall_x(y - 0.075, z + 0.03, 0.0)
    placard(m, V((wxp, y - 0.075, z + 0.03)), V((0, -1, 0)), V((0, 0, 1)), V((-1, 0, 0)), 0.060, 0.030, 'cockplate', off=0.003)
    tube_line(m, [V((wx - 0.020, YB - 0.004, 0.06)), V((wx - 0.020, -0.38, 0.05)), pc + V((0.0, 0.0, -0.070))], 0.0045, 'ck_brass', N=6)
    # main fuel cock low right (big brass body with a long lever) and the gravity-tank cock above it
    y, z = -0.62, -0.30
    wx = wall_x(y, z, 0.0)
    fc = V((wx - 0.040, y, z))
    lathe(m, [(0.022, -0.030), (0.026, -0.022), (0.026, 0.022), (0.018, 0.030)], fc, V((-1, 0, 0)), 'ck_brass', N=16)
    lv = [fc + V((-0.030, 0, 0)), fc + V((-0.040, 0.040, 0.050)), fc + V((-0.044, 0.060, 0.120))]
    tube_line(m, lv, 0.0065, 'ck_brass', N=8)
    lathe(m, [(0.008, 0.0), (0.012, 0.010), (0.010, 0.026)], lv[-1], (lv[-1] - lv[-2]).normalized(), 'ck_brass', N=10)
    tube_line(m, [fc + V((0.0, 0.0, -0.024)), fc + V((0.0, 0.05, -0.12)), V((wx - 0.04, -0.50, S.FLOOR_Z + 0.02))], 0.0055, 'ck_brass', N=6)
    tube_line(m, [fc + V((0.0, -0.024, 0.0)), V((wx - 0.035, -0.70, -0.10)), V((wx - 0.028, -0.70, 0.07))], 0.0045, 'ck_brass', N=6)
    bbox(m, V((wx - 0.010, y, z)), (0.020, 0.07, 0.07), 'ck_crinkle', bev=0.004)
    y, z = -0.70, 0.10
    wx = wall_x(y, z, 0.0)
    gc = V((wx - 0.026, y, z))
    lathe(m, [(0.014, -0.020), (0.016, -0.014), (0.016, 0.014), (0.012, 0.020)], gc, V((-1, 0, 0)), 'ck_brass', N=12)
    axes_box(m, gc + V((-0.024, 0.0, 0.0)), V((0, 1, 0)), V((0, 0, 1)), V((-1, 0, 0)), (0.060, 0.012, 0.010), 'ck_brass', bev=0.003)
    bbox(m, V((wx - 0.008, y, z)), (0.016, 0.050, 0.050), 'ck_crinkle', bev=0.003)
    # oxygen regulator (black round box with a dial) and its hose to the seat side
    y, z = -1.00, 0.30
    wx = wall_x(y, z, 0.0)
    oc = V((wx - 0.024, y, z))
    lathe(m, [(0.040, 0.020), (0.044, 0.012), (0.044, -0.012), (0.040, -0.024)], oc, V((-1, 0, 0)), 'ck_crinkle', N=24)
    disc_face(m, oc + V((-0.0205, 0, 0)), V((0, -1, 0)), V((0, 0, 1)), 0.030, 'oxygen', V((-1, 0, 0)), N=24)
    lathe(m, [(0.034, 0.0), (0.034, 0.004), (0.031, 0.006)], oc + V((-0.020, 0, 0)), V((-1, 0, 0)), 'ck_alu', N=24, cap1=False)
    lathe(m, [(0.010, 0.0), (0.010, 0.016)], oc + V((0, 0, 0.040)), V((0, 0, 1)), 'ck_alu', N=10)
    hose = [oc + V((-0.010, -0.030, -0.035)), oc + V((-0.030, -0.060, -0.12)), V((wx - 0.07, -1.06, -0.04)), V((0.226, -1.08, -0.04))]
    tube_line(m, hose, 0.009, 'ck_rubber', N=8)
    tube_line(m, [oc + V((0.0, 0.040, 0.0)), V((wx - 0.012, -0.80, 0.38)), V((wx - 0.012, -0.50, 0.40)), V((wx - 0.012, YB - 0.004, 0.40))], 0.0045, 'ck_alu', N=6)
    # wall data card (fuel system)
    y, z = -0.88, -0.10
    wx = wall_x(y, z, 0.0)
    placard(m, V((wx, y, z)), V((0, -1, 0)), V((0, 0, 1)), V((-1, 0, 0)), 0.090, 0.045, 'wallcard1', off=0.003)
    # electrical cable loom along the upper longeron (black) with clips
    lp = [V((wall_x(y, 0.42, 0.034), y, 0.42)) for y in (YB - 0.004, -0.40, -0.60, -0.80, -1.00, -1.25)]
    tube_line(m, lp, 0.006, 'ck_rubber', N=6)
    for p in lp[1:-1]:
        bbox(m, p + V((0.012, 0, 0)), (0.020, 0.012, 0.016), 'ck_alu', bev=0.002, seg=1)
    return m


# Aldis sight (1.2.2). In 1.2.1 the tube (x 0.15, z 0.715-0.735, y -0.46..0.55) and the ring sight (x 0.22, z 0.76) sat inside the
# HUD's right text block (vertical speed / altitude / throttle: az ~+8..+19 deg, el ~-4..+4 deg in the game shot ck_air2_fwd) and the
# eyecup was 21 deg right at -4 deg. A tube parallel to the gun line projects onto a line toward the view centre with slope
# (eye height - tube height) / offset, so it can only clear the text block if it sits LOW (on the decking, through the bottom of the
# windscreen) and stops short of the centre: tube x 0.21, z 0.625, eyecup y -0.43, front end y 0.12 (~0.58 m with the eyecup; the
# real tube was longer - shortened as a game compromise). check_nimrod_model.py tests the HUD keep-out boxes from the eye.
ALDIS_X = 0.21      # tube centre line (right of the pilot's eye line)
ALDIS_Z = 0.625     # tube centre height (eye 0.745; the windscreen bottom rail is at 0.600)
ALDIS_Y = (-0.40, 0.12)   # tube rear / front end (eyecup behind the rear end)
RING_SIGHT = False  # 1.2.1 ring-and-bead (x 0.22, ring at z 0.76) sat in the same HUD text block; removed in 1.2.2


def build_sight_and_screen():
    """windscreen glass, its frame, and the Aldis sight as a separate mesh (cockpit_aldis, so the checks can find it)."""
    ws = MeshBuf()
    fr = MeshBuf()
    al = MeshBuf()
    # 1.4.0 (user review 2, shot 8 / 17: 'overly extended'): the reference's small three-pane screen. Centre pane x +-0.15, raked 0.06 m,
    # top 0.71; side panes back to x +-0.26 at y -0.45, top falling to 0.66; bottom edge on the decking (1.3.x: +-0.22, top 0.83)
    import nimrod_structure as STc
    wy, wz1 = S.WS_Y, S.WS_TOP_Z
    def deck(x, y):
        return STc.fus_z(abs(x), y, top=True) - 0.004
    yb_s, yt_s = -0.45, -0.465
    pts = [V((-S.WS_BOT_HW, yb_s, deck(S.WS_BOT_HW, yb_s))), V((-S.WS_TOP_HW, wy, deck(S.WS_TOP_HW, wy))),
           V((S.WS_TOP_HW, wy, deck(S.WS_TOP_HW, wy))), V((S.WS_BOT_HW, yb_s, deck(S.WS_BOT_HW, yb_s)))]
    tops = [V((-S.WS_BOT_HW + 0.03, yt_s, wz1 - 0.05)), V((-S.WS_TOP_HW, wy - 0.06, wz1)), V((S.WS_TOP_HW, wy - 0.06, wz1)), V((S.WS_BOT_HW - 0.03, yt_s, wz1 - 0.05))]
    wz0 = pts[1].z
    for a, b, c, d in zip(pts, pts[1:], tops[1:], tops):
        oriented_quad(ws, [a, b, c, d], 'glass', V((0, 1, 0.3)))
    for a, b in list(zip(tops, tops[1:])) + list(zip(pts, tops)):
        tube_line(fr, [a, b], 0.0055, 'ck_crinkle', N=6)
    for a, b in zip(pts, pts[1:]):                                       # bottom rail on the decking
        tube_line(fr, [a + V((0, 0, 0.004)), b + V((0, 0, 0.004))], 0.0055, 'ck_crinkle', N=6)
    ax, az = ALDIS_X, ALDIS_Z
    y0, y1 = ALDIS_Y
    tube_line(al, [V((ax, y0, az)), V((ax, y1, az))], 0.024, 'ck_crinkle', N=14)
    lathe(al, [(0.031, 0.0), (0.033, 0.010), (0.031, 0.030)], V((ax, y0 - 0.03, az)), V((0, 1, 0)), 'ck_rubber', N=14)
    lathe(al, [(0.028, 0.0), (0.028, 0.012)], V((ax, y1, az)), V((0, 1, 0)), 'ck_crinkle', N=14)          # objective collar
    for yy in (y0 + 0.05, y1 - 0.06):                                                                   # two clamps + feet on the decking
        zt = max(p.z for p in fus_ring(yy, 96) if abs(p.x - ax) < 0.03)
        if az - 0.024 > zt:
            tube_line(al, [V((ax, yy, az - 0.020)), V((ax, yy, zt - 0.004))], 0.006, 'ck_crinkle', N=6)
        bbox(al, V((ax, yy, az)), (0.060, 0.016, 0.060), 'ck_crinkle', bev=0.004, seg=1)
    if RING_SIGHT:
        rr = circle_pts(V((0.22, 0.10, 0.76)), V((0, 1, 0)), 0.055, 16)
        tube_line(fr, rr, 0.0025, 'ck_crinkle', N=4, closed=True)
        zt = max(p.z for p in fus_ring(0.10, 96) if abs(p.x - 0.22) < 0.02)
        tube_line(fr, [V((0.22, 0.10, zt - 0.004)), V((0.22, 0.10, 0.705))], 0.005, 'ck_crinkle', N=6)
        zb = max(p.z for p in fus_ring(1.10, 96) if abs(p.x - 0.22) < 0.02)
        tube_line(fr, [V((0.22, 1.10, zb - 0.025)), V((0.22, 1.10, zb + 0.04))], 0.004, 'ck_crinkle', N=6)
    return ws, fr, al, (wy, wz0)


# =========================================================================================== assemble
def build_cockpit():
    parts = []
    shell = build_shell()
    panel, movers = build_panel()
    comp, card = build_compass()
    ws, sight, aldis, (wy, wz0) = build_sight_and_screen()
    props = [('cockpit_coaming', build_coaming()), ('cockpit_frame', build_frames()), ('cockpit_panel', panel), ('cockpit_compass', comp),
             ('cockpit_breech_L', build_breech(-1)), ('cockpit_breech_R', build_breech(1)), ('cockpit_quadrant', build_quadrant()),
             ('cockpit_trimwheel', build_trimwheel()), ('cockpit_wall_L', build_wall_left()), ('cockpit_wall_R', build_wall_right()),
             ('cockpit_floor', build_floor()), ('cockpit_sight', sight), ('cockpit_aldis', aldis)]
    parts.append(Part('cockpit_interior', 'fus_center', (0, -0.70, 0.0), shell))
    for name, mb in props:
        vs = mb.verts
        c = V((sum(v.x for v in vs) / len(vs), sum(v.y for v in vs) / len(vs), sum(v.z for v in vs) / len(vs)))
        parts.append(Part(name, 'fus_center', c, mb, info=dict(kind='cockpit_prop')))
    parts.append(Part('cockpit_seat', 'fus_center', (0, -0.90, -0.14), build_seat(), info=dict(kind='cockpit_prop')))
    parts.append(Part('cockpit_throttle', 'fus_center', V((THROTTLE_X, QUAD_PIVOT.y, QUAD_PIVOT.z)), build_throttle(),
                      info=dict(kind='lever', drive='Cockpit.Throttle rotation, range 40 (+ = top forward)')))
    parts.append(Part('cockpit_stick', 'fus_center', STICK_PIVOT, build_stick(), info=dict(kind='stick', drive='Cockpit.Joystick range 14')))
    if RUDDER_BAR:
        parts.append(Part('cockpit_rudderbar', 'fus_center', RUDDER_PIVOT, build_rudderbar(), frame=frame_x(V((0, 0, 1)), V((0, -1, 0))),
                          info=dict(kind='rudderbar', drive='ControlSurface yawRange (local +X Unity = up)')))
    # compass card mover
    cp = L.COMPASS
    cc = V((cp['x'], cp['y'], cp['z']))
    parts.append(Part('gauge_compass', 'cockpit_gauges', cc, None, frame_x(V((0, 0, 1)), V((0, 1, 0))), info=dict(kind='gauge')))
    pcard = Part('gauge_compass_card', 'gauge_compass', cc, card, frame_x(V((0, 0, 1)), V((0, 1, 0))),
                 info=dict(kind='gauge_card', axis_local='+X (Unity) = up', **L.SCALES['compass']))
    pcard.own_uv = True
    parts.append(pcard)
    # compact retrofit tac screen quad (MFD material slot 'screen'), just behind the bezel lip
    mfd = MeshBuf()
    t = L.TAC
    c = pp(t['x'], t['h'], 0.0062)
    w, h = t['w'] / 2, t['hgt'] / 2
    q = [c - X_ * w - PU * h, c + X_ * w - PU * h, c + X_ * w + PU * h, c - X_ * w + PU * h]
    oriented_quad(mfd, q, 'screen', PN, uv=[(0, 0), (1, 0), (1, 1), (0, 1)])
    parts.append(Part('mfd_center', 'cockpit_gauges', c, mfd, frame_x(PN, PU), info=dict(kind='mfd', note='stock tacScreenDisplay; 0-1 UVs')))
    parts.insert(0, Part('cockpit_gauges', 'fus_center', P0, None, info=dict(kind='group')))
    parts.append(Part('windscreen', 'fus_center', (0, wy, wz0), ws))
    parts.append(Part('cockpit_eye', 'fus_center', S.EYE, info=dict(kind='crew_eye', crew='pilot')))
    parts += movers
    return parts
