"""B-17G round 5 (user review 2, 2026-11-06): procedural replacements for the rejected fal parts + the missing detail and internals.

Every builder returns Part objects (blender/v2/b25h_parts.Part: world-space MeshBuf in the rest pose). Nothing here is traced or ported
from the War Thunder reference; its proportions were MEASURED (numbers only, nuclearoption-ref/study/b17g) and the shapes follow the
real equipment (Hamilton Standard 23E50 hydromatic prop, Bendix chin turret, Sperry ball and upper turrets, Cheyenne tail position).

- props: hub + 3 blades about the shaft axis (the fal prop was centred by its bounding box: spinner tip 0.21 m and blade-root circle
  0.17 m off the spin axis, one blade 0.47 m short; measured on 1.7.4, docs/b17g_design.md 17)
- turrets: bodies keep the names the Unity check expects (topturret_body, ballturret_body, chinturret_body, tailmantlet_body)
- internals (structure submesh of the part that carries them, so they show when it breaks): wing spars + ribs, fuel cells, fuselage
  frames + stringers, bomb-bay racks + beams, engine accessory sections + mounts, turbo-superchargers, oil tanks.
"""
import math, os
from mathutils import Vector as V, Quaternion, Matrix
import b17g_spec as S
from b25h_geom import MeshBuf, planar_uv, circle_pts, loft, fan_cap, annulus, oriented_quad, cylinder, box, Station, box_ring, section_cap
from b25h_parts import Part
import nimrod_structure as NS

# ============================================================================================ prop texture (own art, 4 flat cells)
PROP_TEX = 'b17g_pr_hsprop_b.png'
UV_BLACK, UV_YELLOW, UV_HUB, UV_STEEL = (0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75)
PROP_CELLS = {UV_BLACK: (0.035, 0.035, 0.035), UV_YELLOW: (0.86, 0.63, 0.08), UV_HUB: (0.46, 0.47, 0.48), UV_STEEL: (0.16, 0.16, 0.17)}


def write_prop_texture(path):
    """64 x 64 PNG with four flat colour cells (prop black, tip yellow, hub grey, dark steel) sampled at the cell centres."""
    import bpy
    n = 64
    im = bpy.data.images.new('hsprop', n, n, alpha=False)
    px = [0.0] * (n * n * 4)
    for (u, v), col in PROP_CELLS.items():
        x0, y0 = int((u - 0.25) * n), int((v - 0.25) * n)      # Blender image rows start at v = 0 (bottom)
        for y in range(y0, y0 + n // 2):
            for x in range(x0, x0 + n // 2):
                k = (y * n + x) * 4
                px[k:k + 4] = [col[0], col[1], col[2], 1.0]
    im.pixels = px
    im.filepath_raw = path; im.file_format = 'PNG'
    im.save()
    bpy.data.images.remove(im)


# ============================================================================================ props
HUB_DOME = [(0.055, 0.158), (0.13, 0.158), (0.19, 0.150), (0.24, 0.128), (0.275, 0.096), (0.298, 0.058), (0.308, 0.022), (0.310, 0.0)]


def blade_mesh(R=S.PROP_R):
    """Hamilton Standard 6477A-0 style blade along local +Z from the hub centre: round shank, broad paddle, rounded tip, yellow tip
    band; twist 52 -> 21 deg; leading edge toward +X (the B-25H convention, proven in game: clockwise seen from behind)."""
    mb = MeshBuf()
    rs = [0.205, 0.30, 0.36, 0.44, 0.56, 0.72, 0.90, 1.08, 1.26, 1.44, 1.58, 1.665, 1.715, 1.745, 1.760]
    chord = [(0.205, 0.120), (0.30, 0.120), (0.36, 0.13), (0.44, 0.20), (0.56, 0.265), (0.72, 0.295), (0.95, 0.305), (1.25, 0.300),
             (1.45, 0.282), (1.58, 0.255), (1.665, 0.215), (1.715, 0.170), (1.745, 0.120), (1.760, 0.060)]
    tcr = [(0.205, 1.0), (0.30, 1.0), (0.36, 0.85), (0.44, 0.40), (0.56, 0.22), (0.80, 0.13), (1.20, 0.09), (1.76, 0.06)]
    beta = [(0.205, 52.0), (0.44, 50.0), (0.80, 36.0), (1.30, 26.0), (1.76, 21.0)]
    def tab(t, x):
        return S.interp(t, x)
    rings, mats_ = [], []
    N = 12
    for r in rs:
        c, tc, b = tab(chord, r), tab(tcr, r), math.radians(tab(beta, r))
        tdir = V((math.cos(b), math.sin(b), 0))          # TE -> LE: tangential (+X) tilted forward (+Y)
        ndir = V((-math.sin(b), math.cos(b), 0))         # thrust face normal
        pts = []
        for k in range(N):
            a = 2 * math.pi * k / N
            x = 0.5 * math.cos(a)
            camber = 0.0 if tc > 0.5 else 0.035 * (1 - (2 * x) ** 2)
            yv = 0.5 * tc * math.sin(a) * (1.0 + (0.0 if tc > 0.5 else 0.28 * math.cos(a))) + camber
            pts.append(V((0, 0, r)) + tdir * (x * c) + ndir * (yv * c))
        rings.append(pts)
    tip0 = 1.615
    nseg = len(rings) - 1
    def fm(i, j):
        return 'pr_hsprop'
    grid, flip = loft(mb, rings, 'pr_hsprop', face_mat=fm)
    for f in mb.faces:      # UV: the blade black, the outer 0.15 m yellow (Hamilton Standard tip band)
        zc = sum(mb.verts[i].z for i in f['idx']) / len(f['idx'])
        f['uv'] = [UV_YELLOW if zc > tip0 else UV_BLACK] * len(f['idx'])
    n0 = len(mb.faces)
    fan_cap(mb, rings[-1], sum(rings[-1], V()) / N + V((0, 0, 0.004)), 'pr_hsprop', V((0, 0, 1)))
    fan_cap(mb, rings[0], sum(rings[0], V()) / N, 'pr_hsprop', V((0, 0, -1)))
    for k, f in enumerate(mb.faces[n0:]):
        f['uv'] = [UV_YELLOW if k < N else UV_STEEL] * len(f['idx'])
    return mb


def hub_mesh(c):
    """23E50 hydromatic hub at c (axis +Y): dome, barrel with three blade sockets and clamp rings, rear cone into the nose case."""
    mb = MeshBuf()
    ax = V((0, 1, 0))
    N = 28
    rings = [circle_pts(c + ax * d, ax, max(r, 0.003), N) for d, r in HUB_DOME]
    loft(mb, rings, 'pr_hsprop')
    fan_cap(mb, rings[-1], c + ax * HUB_DOME[-1][0], 'pr_hsprop', ax)
    # barrel (spider housing) + rear cone (behind the blade plane) down to the shaft
    prof = [(0.055, 0.170), (0.035, 0.192), (-0.075, 0.192), (-0.095, 0.172), (-0.150, 0.135), (-0.205, 0.118)]
    rr = [circle_pts(c + ax * d, ax, r, N) for d, r in prof]
    loft(mb, rr, 'pr_hsprop')
    fan_cap(mb, rr[-1], c + ax * prof[-1][0], 'pr_hsprop', -ax)
    annulus(mb, rings[0], rr[0], 'pr_hsprop', ax)
    for k in range(3):        # blade sockets with clamp rings (the blade shank enters at r 0.205)
        a = 2 * math.pi * k / 3
        d = V((math.sin(a), 0, math.cos(a)))
        cylinder(mb, c + d * 0.13, c + d * 0.215, 0.078, N=16, mat='pr_hsprop', cap0=False)
        cylinder(mb, c + d * 0.17, c + d * 0.196, 0.088, N=16, mat='pr_hsprop')
    for f in mb.faces:
        f['uv'] = [UV_HUB] * len(f['idx'])
    return mb


def build_props():
    """prop_hub_n (child of prop_n, origin ON the shaft axis) + prop_hub_n_blade1..3 (children of the hub, local +Z radial)."""
    out = []
    for (side, kind), num in S.ENGINE_NUM.items():
        xa, za, ylip, yprop, R, yend, zb = S.NACELLES[kind]
        c = V((xa * side, yprop, za))
        out.append(Part(f'prop_hub_{num}', f'prop_{num}', pivot=c, mesh=hub_mesh(c), info={'kind': 'prop_hub', 'spin_axis': 'local +Y (Unity +Z)'}))
        bm = blade_mesh()
        if S.PROP_TURN[num] < 0:      # 1.7.8: counter-rotating prop: blade mirrored across its radial / axis plane (leading edge to -X)
            mir = MeshBuf()
            mir.verts = [V((-p.x, p.y, p.z)) for p in bm.verts]
            mir.faces = [dict(f, idx=list(reversed(f['idx'])), uv=(list(reversed(f['uv'])) if f.get('uv') else f.get('uv'))) for f in bm.faces]
            bm = mir
        for k in range(3):
            ang = 2 * math.pi * k / 3 + math.radians(20)      # parked 20 deg off the vertical (no blade straight down at the ground)
            q = Quaternion(V((0, 1, 0)), ang)
            mb = MeshBuf()
            mb.verts = [c + q @ p for p in bm.verts]
            mb.faces = [dict(f) for f in bm.faces]
            out.append(Part(f'prop_hub_{num}_blade{k + 1}', f'prop_hub_{num}', pivot=c, mesh=mb, frame=q,
                            info={'kind': 'blade', 'pitch_axis_local': '+Z (Blender) = +Y (Unity), radial'}))
    return out


# ============================================================================================ turrets (procedural hard surface)
def ellipsoid(mb, c, frame, radii, thetas, nlon, mat_fn, phase=0.0, outward=True):
    """rings at polar angles `thetas` (deg, 0 = the pole along frame[0]) of the ellipsoid c + rp cos t P + rx sin t cos f X +
    ry sin t sin f Y; mat_fn(theta_mid, phi_mid) -> material per face. Returns the rings."""
    # the pole rings (theta 0 / 180) would be collapsed loops (zero-area triangles, stray check): fan caps to the pole points instead
    inner = [t for t in thetas if 1e-6 < t < 180 - 1e-6]
    rings = [[surf_pt(c, frame, radii, t, phase + 2 * math.pi * k / nlon) for k in range(nlon)] for t in inner]
    def fm(i, j):
        return mat_fn((inner[i] + inner[i + 1]) / 2, phase + 2 * math.pi * (j + 0.5) / nlon)
    loft(mb, rings, 'paint', outward=outward, face_mat=fm)
    if thetas[0] < 1e-6:
        fan_cap(mb, rings[0], surf_pt(c, frame, radii, 0.0, 0.0), mat_fn(inner[0] / 2, 0.0), surf_pt(c, frame, radii, 0.0, 0.0) - c)
    if thetas[-1] > 180 - 1e-6:
        fan_cap(mb, rings[-1], surf_pt(c, frame, radii, 180.0, 0.0), mat_fn(180.0, 0.0), surf_pt(c, frame, radii, 180.0, 0.0) - c)
    return rings


def surf_pt(c, frame, radii, t_deg, f_rad):
    P, X, Y = frame
    rp, rx, ry = radii
    tr = math.radians(t_deg)
    return c + P * (rp * math.cos(tr)) + X * (rx * math.sin(tr) * math.cos(f_rad)) + Y * (ry * math.sin(tr) * math.sin(f_rad))


def surf_nrm(c, frame, radii, p):
    P, X, Y = frame
    rp, rx, ry = radii
    d = p - c
    return (P * (d.dot(P) / rp ** 2) + X * (d.dot(X) / rx ** 2) + Y * (d.dot(Y) / ry ** 2)).normalized()


def slot_strip(mb, pts, nrms, w, proud=0.004, lip=0.016, mat_lip='paint'):
    """gun slot along a surface polyline: a dark strip just proud of the surface between two raised lips (no boolean cut)."""
    for (a, b), (na, nb) in zip(zip(pts, pts[1:]), zip(nrms, nrms[1:])):
        n_ = (na + nb).normalized()
        d = (b - a).normalized(); s = d.cross(n_).normalized()
        q = [a - s * w / 2 + na * proud, b - s * w / 2 + nb * proud, b + s * w / 2 + nb * proud, a + s * w / 2 + na * proud]
        oriented_quad(mb, q, 'metal_dark', n_)
        for sg in (-1, 1):
            NS.sec_tube(mb, a + s * sg * (w / 2 + lip / 2) + na * 0.006, b + s * sg * (w / 2 + lip / 2) + nb * 0.006, lip, 0.012, n_, mat=mat_lip)


def frame_poly(mb, pts, centre, w=0.020, h=0.012, lift=0.005, closed=False, mat='paint'):
    """riveted frame bar along a polyline on a curved surface (normal = away from `centre`)."""
    seq = pts + pts[:1] if closed else pts
    for a, b in zip(seq, seq[1:]):
        n_ = ((a + b) / 2 - centre).normalized()
        NS.sec_tube(mb, a + n_ * lift, b + n_ * lift, w, h, n_, mat=mat)


def inner_copy(mb, faces, centre, off, mat=None):
    """reversed copy of `faces` `off` toward `centre` (glass / housing seen from inside)."""
    for f in faces:
        P_ = [mb.verts[k] for k in f['idx']]
        n_ = (sum(P_, V()) / len(P_) - centre).normalized()
        mb.face([mb.v(p - n_ * off) for p in reversed(P_)], mat or f['mat'], None)


def se_xy(a, hw, hl, n, front_k=1.0):
    ca, sa = math.cos(a), math.sin(a)
    x = hw * math.copysign(abs(sa) ** (2 / n), sa)
    y = hl * math.copysign(abs(ca) ** (2 / n), ca)
    return x, (y * front_k if y > 0 else y)


def _runs_outside(pts, slots, c, pad, closed=True):
    """1.8.13 r2: split a frame polyline into runs that stay clear of the front gun slots (x0 - pad .. x1 + pad, front half)."""
    def inside(p):
        return (p.y - c.y) > 0 and any(x0 - pad < p.x - c.x < x1 + pad for x0, x1, _, _ in slots)
    n = len(pts)
    if closed:
        k0 = next((k for k in range(n) if inside(pts[k])), None)
        if k0 is None:
            return [list(pts) + [pts[0]]]
        order = [pts[(k0 + i) % n] for i in range(n + 1)]
    else:
        order = list(pts)
    runs, cur = [], []
    for p in order:
        if inside(p):
            if len(cur) >= 2:
                runs.append(cur)
            cur = []
        else:
            cur.append(p)
    if len(cur) >= 2:
        runs.append(cur)
    return runs


def slotted_lathe(mb, c, hw, hl, n, prof, slots, mat_fn, front_k=1.0, N=40, depth=0.055, cap_top=True, cap_bot=True, open_back=False, rim=0.0, end_top=True):
    """vertical lathe with a superellipse plan (half widths hw, hl; front (+y) scaled by front_k) through prof = [(scale, z)], with
    vertical gun slots cut into the front: slots = [(x0, x1, z0, z1)] (the rings at z0 / z1 must be in prof; the param angles of the
    slot edges are sampled exactly, so the cut edges are straight). Each slot gets a dark channel `depth` deep. mat_fn(z) -> mat."""
    angs = [2 * math.pi * k / N for k in range(N)]
    for x0, x1, z0, z1 in slots:
        for xe in (x0, x1):
            sa = math.copysign((abs(xe) / hw) ** (n / 2), xe)
            angs.append(math.asin(max(-1.0, min(1.0, sa))) % (2 * math.pi))
    angs = sorted(set(round(a_, 9) for a_ in angs))
    M = len(angs)

    def ring(sc, z, aa=None):
        out = []
        for a_ in (aa or angs):
            x, y = se_xy(a_, hw * sc, hl * sc, n, front_k)
            out.append(V((c.x + x, c.y + y, z)))
        return out
    zs = [z for sc, z in prof]
    if open_back:
        # 1.8.13 r2: the slot edges sit at their exact x on EVERY ring (a ring of smaller scale needs a larger angle for the same x: with one
        # angle set the slots narrowed and slid inboard down the rounded bottom, into the jackets' path); base angles near any edge are
        # dropped so all rings keep one topology
        def edge_ang(xe, sc):
            sa = math.copysign(min(1.0, (abs(xe) / (hw * sc)) ** (n / 2)), xe)
            return math.asin(sa) % (2 * math.pi)
        edges = [(xe, min(z0, z1), max(z0, z1)) for x0, x1, z0, z1 in slots for xe in (x0, x1)]
        scmax = max(sc for sc, z in prof)
        # rings outside a slot's z range keep the full-scale edge angle (no slot cells there; the slot range must stay where the ring is
        # wider than the slot edge)
        per = [[edge_ang(xe, sc) if za - 1e-6 <= z <= zb + 1e-6 else edge_ang(xe, scmax) for xe, za, zb in edges] for sc, z in prof]
        base = [2 * math.pi * k / N for k in range(N)]
        def near(a_):
            for k in range(len(edges)):
                vals = [per[r][k] for r in range(len(prof))]
                lo, hi = min(vals) - math.radians(2.5), max(vals) + math.radians(2.5)
                if lo <= a_ <= hi or lo <= a_ + 2 * math.pi <= hi or lo <= a_ - 2 * math.pi <= hi:
                    return True
            return False
        base = [a_ for a_ in base if not near(a_)]
        ring_angs = [sorted(base + per[r]) for r in range(len(prof))]
        edge_idx = [[ring_angs[r].index(per[r][k]) for k in range(len(edges))] for r in range(len(prof))]
        angs = ring_angs[[sc for sc, z in prof].index(max(sc for sc, z in prof))]
        M = len(angs)
        rings = [ring(sc, z, ring_angs[r]) for r, (sc, z) in enumerate(prof)]
    else:
        rings = [ring(sc, z) for sc, z in prof]

    def in_slot(i, j):
        if i < 0 or i >= len(rings) - 1:
            return False
        zm = (zs[i] + zs[i + 1]) / 2
        if open_back:      # the cell's own corners decide (exact edges on every ring)
            j1 = (j + 1) % M
            q = (rings[i][j] + rings[i][j1] + rings[i + 1][j] + rings[i + 1][j1]) / 4
            x, y = q.x - c.x, q.y - c.y
        else:
            a_ = (angs[j] + angs[(j + 1) % M] + (2 * math.pi if j == M - 1 else 0)) / 2
            x, y = se_xy(a_, hw, hl, n, front_k)
        return any(x0 < x < x1 and min(z0, z1) < zm < max(z0, z1) and y > 0 for x0, x1, z0, z1 in slots)
    loft(mb, rings, 'paint', keep=lambda i, j: not in_slot(i, j), face_mat=lambda i, j: mat_fn((zs[i] + zs[i + 1]) / 2))
    if cap_bot:
        fan_cap(mb, rings[0], V((c.x, c.y, zs[0])), mat_fn(zs[0]), V((0, 0, -1)))
    if cap_top:
        fan_cap(mb, rings[-1], V((c.x, c.y, zs[-1])), mat_fn(zs[-1]), V((0, 0, 1)))

    def inset(p):
        if open_back:      # r2: the walls run straight back along the gun line (radial walls converged into the jackets' path)
            return p - V((0, depth, 0))
        d = V((c.x - p.x, c.y - p.y, 0))
        return p + d.normalized() * depth if d.length > 1e-6 else p
    cells = [(i, j) for i in range(len(rings) - 1) for j in range(M) if in_slot(i, j)]
    for i, j in cells:
        j1 = (j + 1) % M
        a0, b0, a1, b1 = rings[i][j], rings[i][j1], rings[i + 1][j], rings[i + 1][j1]
        if not open_back:          # 1.8.13 r2: open slots (the gun passes through), only the side / end walls
            oriented_quad(mb, [inset(a0), inset(b0), inset(b1), inset(a1)], 'metal_dark', V((a0.x - c.x, a0.y - c.y, 0)))
        if not in_slot(i, (j - 1) % M):
            oriented_quad(mb, [a0, a1, inset(a1), inset(a0)], 'metal_dark', b0 - a0)
        if not in_slot(i, j1):
            oriented_quad(mb, [b0, b1, inset(b1), inset(b0)], 'metal_dark', a0 - b0)
        if not in_slot(i - 1, j):
            oriented_quad(mb, [a0, b0, inset(b0), inset(a0)], 'metal_dark', V((0, 0, 1)))
        if not in_slot(i + 1, j) and end_top:      # r4: the top dome's slot has no top end wall (the jacket passes it at 68 deg)
            oriented_quad(mb, [a1, b1, inset(b1), inset(a1)], 'metal_dark', V((0, 0, -1)))
    if open_back and rim > 0:
        # 1.8.13 r3: a thin frame rim along each slot's exact edges and across its ends (the cut reads as one clean slot)
        for s_i in range(len(slots)):
            za, zb = edges[2 * s_i][1], edges[2 * s_i][2]
            rr = [r for r in range(len(prof)) if za - 1e-6 <= zs[r] <= zb + 1e-6]
            for k in (2 * s_i, 2 * s_i + 1):
                pts = [rings[r][edge_idx[r][k]] for r in rr]
                if len(pts) >= 2:
                    frame_poly(mb, pts, c, rim, 0.006, 0.002)
            # (no rim across the slot ends: the gun's block / jacket reaches the ends at the elevation limits)
    return rings, angs


def chin_turret():
    """Bendix chin turret (B-17G): a round drum under the nose (ref: 0.98 m wide, bottom 0.96 m below the datum, rounded bottom
    edge), two vertical gun slots cut in the front at x +-0.27 (ref 0.27-0.29); it turns in azimuth in the race in the nose skin
    and the guns elevate in the slots (-26..+20 deg). Rest aim = +Y (forward)."""
    t = S.TURRETS['chin']; c = V(t['pos'])
    mb = MeshBuf()
    hw = 0.475
    zt = c.z + 0.418
    # round 6 (coordinator: 'a bucket'): a bulbous blister - the side rolls into a rounded bottom from the gun line down (was a flat
    # bottom with a 3 cm radius), 4 cm shallower; the top is faired into the nose by chin_ring's sloped fairing
    prof = [(0.30, c.z - 0.200), (0.55, c.z - 0.192), (0.72, c.z - 0.178), (0.84, c.z - 0.158), (0.92, c.z - 0.135), (0.965, c.z - 0.105),
            (0.99, c.z - 0.07), (1.0, c.z - 0.03), (1.0, c.z + 0.17), (1.0, c.z + 0.30), (1.0, zt)]
    if S.ANM2_SLOTS:       # r2: the rounding starts 2 cm lower (receiver rears at +20 deg); still a rounded blister, not a bucket
        prof = [(0.30, c.z - 0.200), (0.55, c.z - 0.196), (0.72, c.z - 0.188), (0.84, c.z - 0.178), (0.93, c.z - 0.160), (0.97, c.z - 0.130),
                (0.99, c.z - 0.09), (1.0, c.z - 0.04), (1.0, c.z + 0.17), (1.0, c.z + 0.30), (1.0, zt)]
    slots = [(-0.31, -0.235, c.z - 0.135, c.z + 0.17), (0.235, 0.31, c.z - 0.135, c.z + 0.17)]
    if S.ANM2_SLOTS:       # 1.8.13 r2: the AN/M2 jacket at -26 deg leaves through the rounded bottom: slots from the bottom ring up to +0.30
        slots = [(gx - 0.051, gx + 0.051, c.z - 0.188, c.z + 0.30) for gx, _ in t['guns']]     # r3: 92 mm clear inside the 10 mm rims (the 80 mm trunnion block passes at -26)
    nf0 = len(mb.faces)
    slotted_lathe(mb, c, hw, hw, 2.15, prof, slots, lambda z: 'paint', front_k=0.96, depth=0.02 if S.ANM2_SLOTS else 0.06, open_back=S.ANM2_SLOTS, rim=0.010 if S.ANM2_SLOTS else 0.0)   # r2: shallow walls clear the receiver fronts
    if S.ANM2_SLOTS:       # lined inside: through the open slots one sees the turret's inside, not the sky
        inner_copy(mb, [f for f in mb.faces[nf0:] if f['mat'] == 'paint'], V((c.x, c.y, c.z + 0.05)), 0.004, 'interior')
    for dz, w in ((0.02, 0.012), (0.30, 0.010)):          # panel seams (lower band at the start of the rounding / top band), clear of the slots
        ring = [V((c.x + x, c.y + y, c.z + dz)) for x, y in (se_xy(2 * math.pi * k / 48, hw * 1.004, hw * 1.004, 2.15, 0.96) for k in range(48))]
        if dz < 0:
            ring = [p for p in ring if not (p.y > c.y and 0.20 < abs(p.x - c.x) < 0.35)]
        if S.ANM2_SLOTS:   # r2: seams break at the open slots
            for run in _runs_outside(ring, slots, c, 0.012):
                frame_poly(mb, run, V((c.x, c.y, c.z + dz)), w, 0.005, 0.0)
        else:
            frame_poly(mb, ring, V((c.x, c.y, c.z + dz)), w, 0.005, 0.0, closed=dz > 0)
    return [Part('chinturret_body', 'chin_az', mesh=mb, info={'kind': 'turret_body', 'type': 'Bendix chin turret (procedural)'})]


def ball_turret():
    """Sperry ball turret: sphere d 1.12 m (ref 1.10), round armour-glass sighting window in the face between the guns, two small
    side vision windows, gun ports with collars at x +-0.20, trunnion bosses on +-x (the yoke arms), seam and rear door outline.
    Turns with ball_el (the whole ball elevates; the yoke turns with ball_az)."""
    t = S.TURRETS['ball']; c = V(t['pos'])
    r = 0.56
    mb = MeshBuf()
    wdir = V((0, math.cos(math.radians(-8)), math.sin(math.radians(-8))))     # window 8 deg below the gun line
    X = V((1, 0, 0)); Y = wdir.cross(X).normalized()
    frame = (wdir, X, Y)
    WIN = 15.0
    thetas = [0.0, 5.0, 10.0, WIN, WIN + 3.0] + [WIN + 3.0 + (180 - WIN - 3.0) * k / 14 for k in range(1, 15)]
    ellipsoid(mb, c, frame, (r, r, r), thetas, 36, lambda th, ph: 'glass' if th < WIN else 'paint')
    frame_poly(mb, [surf_pt(c, frame, (r, r, r), WIN + 0.8, 2 * math.pi * k / 36) for k in range(36)], c, 0.032, 0.016, 0.006, closed=True)
    for sx in (-1, 1):           # side vision windows: curved framed glass plates up and outboard of the guns
        cen_dir = (wdir * 0.62 + X * (sx * 0.55) + V((0, 0, 1)) * 0.56).normalized()
        u_ = cen_dir.cross(V((0, 0, 1))).normalized(); v_ = u_.cross(cen_dir).normalized()
        grid = [[c + (cen_dir + u_ * ((j / 3 - 0.5) * 0.30) + v_ * ((i / 3 - 0.5) * 0.20)).normalized() * (r + 0.004) for j in range(4)] for i in range(4)]
        for i in range(3):
            for j in range(3):
                q = [grid[i][j], grid[i][j + 1], grid[i + 1][j + 1], grid[i + 1][j]]
                oriented_quad(mb, q, 'glass', sum(q, V()) / 4 - c)
        edge = [grid[0][j] for j in range(4)] + [grid[i][3] for i in range(1, 4)] + [grid[3][j] for j in (2, 1, 0)] + [grid[i][0] for i in (2, 1)]
        frame_poly(mb, edge, c, 0.024, 0.012, 0.004, closed=True)
    fwd = V((0, 1, 0))
    for sx in (-1, 1):           # gun ports (the stock barrels on the gun slots pass through them)
        g = c + X * (sx * 0.20)
        p0 = g + fwd * (math.sqrt(r * r - 0.20 ** 2) - 0.02)
        cylinder(mb, p0 + fwd * 0.012, p0 + fwd * 0.09, 0.046, 0.040, N=14, mat='metal_dark')
        ring_o = circle_pts(p0 + fwd * 0.012, fwd, 0.078, 18); ring_i = circle_pts(p0 + fwd * 0.012, fwd, 0.046, 18)
        annulus(mb, ring_o, ring_i, 'paint', fwd)
        loft(mb, [circle_pts(p0 - fwd * 0.03, fwd, 0.078, 18), ring_o], 'paint')
    for sx in (-1, 1):           # trunnion bosses (the yoke arms sit at x +-0.60)
        cylinder(mb, c + X * (sx * (r - 0.03)), c + X * (sx * 0.595), 0.11, 0.10, N=20, mat='gear')
    seam = [c + V((0, math.cos(a), math.sin(a))) * (r + 0.003) for a in [2 * math.pi * k / 40 for k in range(40)]]
    frame_poly(mb, seam, c, 0.012, 0.006, 0.0, closed=True)
    door = [c + (-fwd * math.cos(math.radians(34)) + (X * math.cos(f) + V((0, 0, 1)) * math.sin(f)) * math.sin(math.radians(34))).normalized() * (r + 0.003)
            for f in [2 * math.pi * k / 24 for k in range(24)]]
    frame_poly(mb, door, c, 0.016, 0.007, 0.0, closed=True)
    inner_copy(mb, [f for f in mb.faces if f['mat'] == 'glass'], c, 0.004)
    return [Part('ballturret_body', 'ball_el', mesh=mb, info={'kind': 'turret_body', 'type': 'Sperry ball turret (procedural)'})]


def top_turret():
    """Sperry A-1 upper turret: a low framed plexiglass dome (round plan, ref 0.96 m wide, top 0.28 m over the pivot = 0.37 m over the
    fuselage) on a painted base band, the two guns at x +-0.30 (ref 0.33) in slots cut into the painted gun mount at the lower front;
    sill band, crown ring, meridian frames. Turns with top_az; replaces the fal ring + the 1.6 hemisphere glass and frames."""
    t = S.TURRETS['top']; c = V(t['pos'])
    hw = 0.47
    ctr = V((c.x, c.y, c.z - 0.05))
    mb = MeshBuf()
    prof = [(0.985, c.z - 0.16), (1.0, c.z - 0.10), (1.012, c.z - 0.085), (1.0, c.z - 0.07), (0.985, c.z - 0.01), (0.955, c.z + 0.05),
            (0.91, c.z + 0.105), (0.85, c.z + 0.15), (0.76, c.z + 0.195), (0.62, c.z + 0.235), (0.43, c.z + 0.262), (0.21, c.z + 0.275)]
    zg = c.z - 0.07           # glazing above the sill band (the roof is at c.z - 0.10 here: ref dome 0.37 m over the roof)
    if S.ANM2_SLOTS:       # 1.8.13 r2 (coordinator decision): the dome 6 cm taller (top 0.275 -> 0.335 over the pivot; the glazing above the sill
        # stretched by 1.174, ring / base / sill / fuselage join unchanged) so the AN/M2 receivers stay inside at 85 deg
        k_ = (0.335 + 0.07) / (0.275 + 0.07)
        prof = [(s_, z_ if z_ <= zg else zg + (z_ - zg) * k_) for s_, z_ in prof]
        prof[0] = (1.0, prof[0][1] - 0.008)     # r4c: the base ring at the race's inner radius and 8 mm lower: it sits in the race (was 6 mm clear)
    slots = [(-0.335, -0.265, c.z - 0.07, c.z + 0.105), (0.265, 0.335, c.z - 0.07, c.z + 0.105)]
    if S.ANM2_SLOTS:       # 1.8.13 r2: the guns elevate to 85 deg: the slots run up the dome front to the crown (Sperry A-1 practice)
        slots = [(gx - 0.040, gx + 0.040, c.z - 0.07, prof[-2][1]) for gx, _ in t['guns']]     # up the dome front to the last ring wider than the slot; r3: 70 mm clear inside the 10 mm rims (jacket + 9 mm a side)
    nf0 = len(mb.faces)
    rings, angs = slotted_lathe(mb, c, hw, hw, 2.2, prof, slots, lambda z: 'glass' if z > zg else 'paint', depth=0.006 if S.ANM2_SLOTS else 0.05, cap_bot=False, open_back=S.ANM2_SLOTS, rim=0.010 if S.ANM2_SLOTS else 0.0, end_top=not S.ANM2_SLOTS)
    for f in mb.faces[nf0:]:      # the gun mount front (around the slots, below z +0.12) is painted armour, not glass
        if f['mat'] != 'glass':
            continue
        P_ = [mb.verts[k] for k in f['idx']]; cc = sum(P_, V()) / len(P_)
        if cc.z < c.z + 0.08 and (cc.y - c.y) > 0.22 and abs(cc.x - c.x) < 0.40:
            n_ = (P_[1] - P_[0]).cross(P_[-1] - P_[0])
            f['mat'] = 'paint'; f['uv'] = [planar_uv(p, n_) for p in P_]
    gl = [f for f in mb.faces[nf0:] if f['mat'] == 'glass']
    inner_copy(mb, gl, ctr, 0.003)
    pm = [f for f in mb.faces[nf0:] if f['mat'] == 'paint' and (S.ANM2_SLOTS or (sum((mb.verts[k] for k in f['idx']), V()) / len(f['idx'])).z > zg)]
    inner_copy(mb, pm, ctr, 0.004, 'interior')
    M = len(angs)
    for run in (_runs_outside(rings[3], slots, c, 0.012) if S.ANM2_SLOTS else [rings[3] + rings[3][:1]]):
        frame_poly(mb, run, ctr, 0.030, 0.014, 0.004)                       # sill
    if S.ANM2_SLOTS:       # r2: the crown ring and the gun-mount edge break at the slots (the jackets pass up through them)
        for run in _runs_outside(rings[8], slots, c, 0.012):
            frame_poly(mb, run, ctr, 0.022, 0.012, 0.004)
    else:
        frame_poly(mb, rings[8], ctr, 0.022, 0.012, 0.004, closed=True)      # crown ring
    for k in range(8):                                                        # meridians (none across the gun mount)
        a_ = 2 * math.pi * k / 8 + math.pi / 8
        j = min(range(M), key=lambda q: abs(((angs[q] - a_ + math.pi) % (2 * math.pi)) - math.pi))
        x, y = se_xy(angs[j], hw, hw, 2.2)
        if y > 0.22 and abs(x) < 0.40:
            continue
        frame_poly(mb, [rr[j] for rr in rings[3:9]], ctr, 0.020, 0.012, 0.004)
    edge = sorted([p for p in rings[6] if (p.y - c.y) > 0.20 and abs(p.x - c.x) < 0.42], key=lambda p: p.x)
    for run in (_runs_outside(edge, slots, c, 0.012, closed=False) if S.ANM2_SLOTS else [edge]):
        frame_poly(mb, run, ctr, 0.024, 0.012, 0.004)                       # top edge of the gun mount
    return [Part('topturret_body', 'top_az', mesh=mb, info={'kind': 'turret_body', 'type': 'Sperry A-1 upper turret (procedural)'})]


TAIL_C = V((0.0, -14.70, S.TAIL_GUN_Z))        # Cheyenne gun mount: cover centre on the azimuth axis (ref: cover x +-0.43, z 0.39..1.05, aft -15.17)
TAIL_R = (0.45, 0.38) if S.TAIL188 else (0.45, 0.31) if S.TAIL_WINDOW else (0.45, 0.42)     # 1.8.8: reference size (z 0.32..1.08, tip -15.15)                  # cover radii: horizontal (x and y: the azimuth turn maps it onto itself), vertical. 1.7.9: 0.40 / 0.33 ->
                                       # 0.45 / 0.42 (reference: the cover is the end of the body - 0.8 m tall at -14.90, tip -15.15; pivot kept)
TAIL_N = 2.6 if S.TAIL188 else 2.0      # 1.8.8: superellipsoid of revolution about the azimuth axis, (r / rh)^n + (|z| / rv)^n = 1 (reference: boxier)
TAIL_CUT = ((-14.84, 0.30), (-14.91, 1.16))   # 1.7.9: nearly upright opening at the end of the body (was -14.81 / 0.35 -> -14.93 / 1.10)   # round 6: lower lip 0.17 m further aft - the skin wraps under the cover (it hung below the fuselage line)   # oblique opening of the fuselage end (y, z) bottom -> top (ref: lip bottom -14.66, top -14.93 at z 1.08)


def tail_plane():
    (y0, z0), (y1, z1) = TAIL_CUT
    d = V((0, y1 - y0, z1 - z0)).normalized()
    n = V((0, d.z, -d.y))                       # forward / up side is kept
    return V((0, y0, z0)), n


def tail_cut(mb, rings):
    """round 5: the tail_gun skin runs on to y -14.95 (FUS table) and is cut by the oblique opening plane (exact straight edge, no
    face sawtooth); the end ring above the cut is closed by the gunner's aft armour-glass window. The cover sits in the opening."""
    p0, n = tail_plane()
    end = rings[-1]
    fan_cap(mb, end, sum(end, V()) / len(end), 'glass', V((0, -1, 0)))
    NS.clip_faces(mb, p0, n)
    # round 6: clip_faces gives every clipped face its own corners; weld them by position so the cut skin shades smoothly (the
    # 'stepped, jagged' lower tail skin in r5_tail_side)
    key = {}
    for f in mb.faces:
        new = []
        for i in f['idx']:
            p = mb.verts[i]; k = (round(p.x, 6), round(p.y, 6), round(p.z, 6))
            if k not in key:
                key[k] = i
            new.append(key[k])
        f['idx'] = new


def tail_lip(mb):
    """rim around the oblique opening (riveted lip, painted) after the double skin closed the cut edge."""
    p0, n = tail_plane()
    pts = []
    for f in mb.faces:
        if f['mat'] != 'paint' and not (S.TAIL188 and f['mat'] == 'glass'):      # 1.8.8: the glazed aft face meets the opening at its top
            continue
        P_ = [mb.verts[k] for k in f['idx']]
        for a, b in zip(P_, P_[1:] + P_[:1]):
            if abs((a - p0).dot(n)) < 1e-5 and abs((b - p0).dot(n)) < 1e-5:
                pts.append((a + b) / 2)
    if S.TAIL188:      # de-duplicate (glass and paint faces share the cut edge points)
        uq = []
        for q in pts:
            if all((q - u).length > 0.004 for u in uq):
                uq.append(q)
        pts = uq
    if len(pts) < 6:
        return 0
    ctr = sum(pts, V()) / len(pts)
    u = n.cross(V((1, 0, 0))).normalized()
    pts.sort(key=lambda p: math.atan2((p - ctr).dot(u), p.x))
    # round 6: collar in the cut plane from the lip in to 12 mm outside the cover (the gap under the cover was a see-through notch);
    # the spheroid is symmetric about the azimuth axis, so its section in this plane does not change when the cover turns
    c, (rh, rv) = TAIL_C, TAIL_R
    cp = c - n * (c - p0).dot(n)
    def f_(p):
        d = p - c
        return (math.hypot(d.x, d.y) / rh) ** TAIL_N + (abs(d.z) / rv) ** TAIL_N
    inner = []
    for L in pts:
        if f_(L) <= 1.0:
            inner.append(L); continue
        lo, hi = 0.0, 1.0
        for _ in range(40):
            m = (lo + hi) / 2
            if f_(cp.lerp(L, m)) < 1.0:
                lo = m
            else:
                hi = m
        q = cp.lerp(L, hi)
        q = q + (L - q).normalized() * min(0.008, (L - q).length)     # 1.7.8: 12 -> 8 mm (check a: the cover must sit within 1 cm of the airframe)
        inner.append(q)
    # 1.8.0: the collar above the cover is the gunner's window (glass both ways, framed), the rest stays painted armour
    ztop = c.z + rv
    win = []
    for k in range(len(pts)):
        a, b, c2, d = pts[k], pts[(k + 1) % len(pts)], inner[(k + 1) % len(pts)], inner[k]
        if (a - d).length < 1e-4 and (b - c2).length < 1e-4:
            continue
        glass = S.TAIL_WINDOW and not S.TAIL188 and (a.z + b.z) / 2 > ztop + 0.02 and min(c2.z, d.z) > c.z      # collar above the cover's top (1.8.8: armour; the cab's aft face is the window)
        oriented_quad(mb, [a, b, c2, d], 'glass' if glass else 'paint', -n)
        oriented_quad(mb, [p + n * 0.005 for p in (a, b, c2, d)], 'glass' if glass else 'interior', n)
        if glass:
            win.append(k)
    frame_poly(mb, pts, ctr, 0.035, 0.018, 0.0, closed=True)
    if win:
        sill = [inner[k] for k in win] + [inner[(win[-1] + 1) % len(pts)]]
        sill.sort(key=lambda p: p.x)
        frame_poly(mb, sill, ctr, 0.030, 0.016, 0.0)                     # sill bar along the cover's top
        lip = sorted([pts[k] for k in win] + [pts[(win[-1] + 1) % len(pts)]], key=lambda p: p.x)
        def at_x(seq, x):
            for p, q in zip(seq, seq[1:]):
                if (p.x - x) * (q.x - x) <= 0 and abs(q.x - p.x) > 1e-6:
                    return p.lerp(q, (x - p.x) / (q.x - p.x))
            return None
        for x in (-0.16, 0.16):                                         # two mullions: three panes (the Cheyenne's framed window)
            lo_, hi_ = at_x(sill, x), at_x(lip, x)
            if lo_ is not None and hi_ is not None:
                NS.sec_tube(mb, lo_ - n * 0.004, hi_ - n * 0.004, 0.026, 0.014, -n, mat='paint')
        STATS_TAIL['window_quads'] = len(win)
        STATS_TAIL['window_z'] = (round(min(p.z for p in sill), 3), round(max(p.z for p in lip), 3))
        STATS_TAIL['window_w'] = round(max(p.x for p in lip) - min(p.x for p in lip), 3)
    return len(pts)


STATS_TAIL = {}


def tail_turret():
    """Cheyenne tail gun mount: a rounded armour cover (oblate spheroid about the azimuth axis, so it can turn +-30 deg inside the
    fuselage end) in the oblique opening, the two guns in vertical slots at x +-0.13 (cut, with dark channel walls).
    Turns with tail_az; the guns elevate in the slots."""
    c = TAIL_C; rh, rv = TAIL_R
    mb = MeshBuf()
    # pole along +X: the latitude rings are the planes x = const, so the slot edges (x = +-0.13 +- 0.03) are exact rings
    X = V((1, 0, 0)); aft = V((0, -1, 0)); Z = V((0, 0, 1))
    SX0, SX1 = (0.094, 0.166) if S.ANM2_SLOTS else (0.10, 0.16)      # 1.8.13 r3: 62 mm clear inside the 10 mm rims round the 52 mm jacket
    SDEP = 0.025 if S.ANM2_SLOTS else 0.06                                # r2: shallow channel walls clear the receiver fronts      # 1.8.13 r2: 76 mm slots round the 52 mm AN/M2 jacket (12 mm a side)
    xs = sorted({s_ * v for s_ in (-1, 1) for v in (rh - 0.001, rh - 0.02, rh - 0.05, 0.34, 0.28, 0.20, SX1, SX0, 0.03)})
    NL = 40
    rings = []
    def _t(x, a):          # distance from the pole axis to the surface in the plane x = const, direction (aft cos a, up sin a)
        lo, hi = 0.0, rh + rv
        for _ in range(40):
            m = (lo + hi) / 2
            if (math.hypot(x, m * math.cos(a)) / rh) ** TAIL_N + (abs(m * math.sin(a)) / rv) ** TAIL_N < 1.0:
                lo = m
            else:
                hi = m
        return lo
    for x in xs:
        if TAIL_N == 2.0:
            s_ = math.sqrt(max(1 - (x / rh) ** 2, 1e-6))
            rings.append([c + X * x + aft * (rh * s_ * math.cos(2 * math.pi * k / NL)) + Z * (rv * s_ * math.sin(2 * math.pi * k / NL)) for k in range(NL)])
        else:
            rings.append([c + X * x + (aft * math.cos(2 * math.pi * k / NL) + Z * math.sin(2 * math.pi * k / NL)) * max(_t(x, 2 * math.pi * k / NL), 1e-4)
                          for k in range(NL)])
    slot_x = [(-SX1, -SX0), (SX0, SX1)]
    def in_slot(i, j):
        xm = (xs[i] + xs[i + 1]) / 2
        a = 2 * math.pi * (j + 0.5) / NL
        a = a if a <= math.pi else a - 2 * math.pi
        return any(x0 < xm < x1 for x0, x1 in slot_x) and abs(a) < math.radians(40)
    loft(mb, rings, 'paint', keep=lambda i, j: not in_slot(i, j))
    fan_cap(mb, rings[0], sum(rings[0], V()) / NL, 'paint', -X)
    fan_cap(mb, rings[-1], sum(rings[-1], V()) / NL, 'paint', X)
    if S.ANM2_SLOTS:
        # 1.8.13 r3: the cover is open on the gunner's side (everything ahead of 2 cm behind its centre is inside the fuselage, so the outside
        # outline does not change): the gunner sees the receivers and grips; r2: lined inside
        mb.faces = [f for f in mb.faces if (sum((mb.verts[k] for k in f['idx']), V()) / len(f['idx']) - c).dot(aft) > -0.02]
        inner_copy(mb, [f for f in mb.faces if f['mat'] == 'paint'], c, 0.004, 'interior')
    # slot channels: back wall 6 cm inside, side walls, end walls (dark)
    for x0, x1 in slot_x:
        i0, i1 = xs.index(x0), xs.index(x1)
        js = [j for j in range(NL) if in_slot(i0, j)]
        js = sorted(js, key=lambda j: (j + NL // 2) % NL)
        def inset(p, d=SDEP):
            return p + (c + X * p.x - p).normalized() * d if (c + X * p.x - p).length > 1e-6 else p
        for j in js:
            j1 = (j + 1) % NL
            a0, b0, a1, b1 = rings[i0][j], rings[i0][j1], rings[i1][j], rings[i1][j1]
            if not S.ANM2_SLOTS:
                oriented_quad(mb, [inset(a0), inset(b0), inset(b1), inset(a1)], 'metal_dark', aft)
            oriented_quad(mb, [a0, b0, inset(b0), inset(a0)], 'metal_dark', X)
            oriented_quad(mb, [a1, b1, inset(b1), inset(a1)], 'metal_dark', -X)
        for j, sgn in ((js[0], -1), ((js[-1] + 1) % NL, 1)):
            a0, a1 = rings[i0][j], rings[i1][j]
            oriented_quad(mb, [a0, a1, inset(a1), inset(a0)], 'metal_dark', Z * sgn * -1)
        if S.ANM2_SLOTS:       # r3: a thin frame rim round each slot
            jj = js + [(js[-1] + 1) % NL]
            for ii in (i0, i1):
                frame_poly(mb, [rings[ii][j] for j in jj], c, 0.010, 0.006, 0.002)
            for j in (jj[0], jj[-1]):
                frame_poly(mb, [rings[i0][j], rings[i1][j]], c, 0.010, 0.006, 0.002)
    # horizontal plate seam across the cover
    band = [c + aft * (rh * math.cos(t)) + X * (rh * math.sin(t)) for t in [math.radians(a) for a in range(-80, 81, 8)]]
    if S.ANM2_SLOTS:       # r2: the seam stops at the open slots (the jackets cross it at 0 deg)
        runs, cur = [], []
        for p in band:
            if any(x0 - 0.012 < p.x - c.x < x1 + 0.012 for x0, x1 in slot_x):
                if len(cur) >= 2:
                    runs.append(cur)
                cur = []
            else:
                cur.append(p)
        if len(cur) >= 2:
            runs.append(cur)
        for run in runs:
            frame_poly(mb, run, c, 0.014, 0.006, 0.002)
    else:
        frame_poly(mb, [p + Z * 0.0 for p in band], c, 0.014, 0.006, 0.002)
    return [Part('tailmantlet_body', 'tail_az', mesh=mb, info={'kind': 'turret_body', 'type': 'Cheyenne tail mount cover (procedural)'})]


# ============================================================================================ internals (user review 2 / 11, 12)
# The stock VT-7 cutaway shows a full skeleton, engine and tanks; the 1.7.4 wreck showed only rib stubs at the seams. Everything below
# goes into the `structure` (aluminium), `tyre` (black rubber fuel cells), `engine`, `exhaust`, `metal_dark` submeshes of the part that
# carries it in the real aircraft, so a part that breaks off shows its own skeleton. All of it sits >= 12 mm inside the outer skin.
SPAR_S = (0.18, 0.62)            # front / rear spar chord fractions (rear spar ahead of the flap / aileron hinge at 0.735)
RIB_STEP = 0.75


def _bar(mb, a, b, w, h, up, mat='structure'):
    """rectangular section bar without end caps (8 tris)."""
    a, b, up = V(a), V(b), V(up).normalized()
    ax = (b - a)
    if ax.length < 1e-5:
        return
    ax.normalize()
    s = ax.cross(up)
    if s.length < 1e-6:
        s = ax.orthogonal()
    s.normalize(); u = s.cross(ax).normalized()
    ra = [a + s * (w / 2) + u * (h / 2), a - s * (w / 2) + u * (h / 2), a - s * (w / 2) - u * (h / 2), a + s * (w / 2) - u * (h / 2)]
    rb = [p + (b - a) for p in ra]
    loft(mb, [ra, rb], mat, smooth=False)


def _inside(st, s, upper, d):
    """point at chord fraction s on the upper / lower contour moved an ABSOLUTE distance d toward the other contour (at most 45 % of
    the local thickness): a fraction poked the bars through the thin outer-wing skin (check b2)."""
    a, b = st.point(s, upper), st.point(s, not upper)
    t = (b - a).length
    return a.lerp(b, min(d / max(t, 1e-6), 0.45))


def _wing_parts_x(side):
    xs_b = [S.WING_ROOT_X] + S.WING_SPLITS + [S.WING_TIP_X]
    s = 'L' if side < 0 else 'R'
    return [(f'wing_{n}_{s}', xs_b[i], xs_b[i + 1]) for i, n in enumerate(('inner', 'mid', 'outer', 'tip'))]


def wing_internals(side, wing_station):
    """front + rear trussed spars (caps + diagonal web tubes, Boeing tubular-truss style), truss ribs every 0.75 m, fuel cells."""
    out = {}
    for name, x0, x1 in _wing_parts_x(side):
        mb = MeshBuf()
        xa, xb = x0 + 0.045, (x1 - 0.045 if not name.startswith('wing_tip') else min(x1, 15.25))     # clear of the seam paint caps (+-0.015)
        n = max(1, int(math.ceil((xb - xa) / RIB_STEP)))
        xs = [xa + (xb - xa) * k / n for k in range(n + 1)]
        sts = [wing_station(x, side) for x in xs]
        for sf in SPAR_S:
            for up in (True, False):
                pts = [_inside(st, sf, up, 0.034) for st in sts]
                for k_, (a, b) in enumerate(zip(pts, pts[1:])):
                    _bar(mb, a, b, 0.06 + 0.008 * (k_ % 2), 0.035 + 0.006 * (k_ % 2), V((0, 0, 1)))
            for k in range(len(sts) - 1):         # web: N truss (vertical + diagonal) per bay
                a_up, a_lo = _inside(sts[k], sf, True, 0.05), _inside(sts[k], sf, False, 0.05)
                b_up, b_lo = _inside(sts[k + 1], sf, True, 0.05), _inside(sts[k + 1], sf, False, 0.05)
                _bar(mb, a_up, a_lo, 0.03, 0.03, V((0, 1, 0)))
                _bar(mb, a_lo, b_up, 0.025, 0.025, V((0, 1, 0)))
            _bar(mb, _inside(sts[-1], sf, True, 0.05), _inside(sts[-1], sf, False, 0.05), 0.03, 0.03, V((0, 1, 0)))
        for st in sts:                            # truss ribs: upper + lower contour from the LE to the rear spar, 3 posts
            ss = [0.10, SPAR_S[0], 0.30, 0.42, 0.52, SPAR_S[1], 0.70]       # (from 10 % chord: near the LE the bars poked through the curved skin)
            for up in (True, False):
                pts = [_inside(st, s_, up, 0.029) for s_ in ss]
                for k_, (a, b) in enumerate(zip(pts, pts[1:])):
                    _bar(mb, a, b, 0.018 + 0.006 * (k_ % 2), 0.03 + 0.006 * (k_ % 2), V((1, 0, 0)))
            for s_ in (0.30, 0.42, 0.52):
                _bar(mb, _inside(st, s_, True, 0.03), _inside(st, s_, False, 0.03), 0.018, 0.02, V((1, 0, 0)))
        out[name] = mb
    # self-sealing fuel cells between the spars (real B-17G: inboard engine tanks, outboard engine tanks, feeders, 9 Tokyo cells)
    cells = [(1.30, 2.22), (3.95, 4.66), (4.84, 5.78), (7.42, 8.80)] + [(9.15 + 0.58 * k, 9.15 + 0.58 * k + 0.50) for k in range(9)]
    for c0, c1 in cells:
        part = next(nm for nm, x0, x1 in _wing_parts_x(side) if x0 <= (c0 + c1) / 2 < x1)
        mb = out[part]
        rings = []
        for x in (c0, (c0 + c1) / 2, c1):
            st = wing_station(x, side)
            s0, s1 = SPAR_S[0] + 0.006, SPAR_S[1] - 0.006      # the cells bear on the spar webs
            top = [_inside(st, s_, True, 0.07) for s_ in (s0, (s0 + s1) / 2, s1)]
            bot = [_inside(st, s_, False, 0.07) for s_ in (s1, (s0 + s1) / 2, s0)]
            rings.append(top + bot)
        loft(mb, rings, 'tyre')
        cap0, cap1 = rings[0], rings[-1]
        for ring_, sgn in ((cap0, -1), (cap1, 1)):
            ctr = sum(ring_, V()) / len(ring_)
            fan_cap(mb, ring_, ctr, 'tyre', V((side * sgn, 0, 0)))
    return out


FRAME_STEP = 0.55


def _fus_part_of(y):
    b = [S.FUS[0][0]] + S.SPLITS + [S.FUS[-1][0]]
    for i, n in enumerate(S.FUS_PARTS):
        if b[i + 1] <= y < b[i]:
            return n
    return None


def _fus_excluded(p, y, dome=True):
    """skip structure where it would cross an opening, a moving part or the cockpit / nose glazing. dome=False: leave the astrodome to
    _dome_spans (1.8.18: frames / stringers clipped on its inner ring instead of stopping 10 cm short with open ends)."""
    T = S.TURRETS
    if 2.85 < y < 4.70 or y > 6.45:                      # pilots' cab (own interior) + nose glazing
        return True
    if (p - V(T['top']['pos'])).length < 0.75 or (p - V(T['ball']['pos'])).length < 1.00 or (p - V(T['chin']['pos'])).length < 0.95:
        return True
    if S.BAY_Y[0] - 0.05 < y < S.BAY_Y[1] + 0.05 and p.z < S.BAY_ROOF_Z + 0.06:
        return True
    if S.TAIL_WELL[0] - 0.12 < y < S.TAIL_WELL[1] + 0.12 and abs(p.x) < 0.40 and p.z < 1.00:
        return True
    if S.RADIO_HATCH[0] - 0.05 < y < S.RADIO_HATCH[1] + 0.05 and p.z > 1.45 and abs(p.x) < 0.55:
        return True
    if y < -14.40:                                         # Cheyenne mount (turns inside the end)
        return True
    for (ya, yb), sx in ((S.WAIST_R, 1), (S.WAIST_L, -1)):   # waist windows (flexible guns)
        if ya - 0.25 < y < yb + 0.25 and p.x * sx > 0.3 and -0.10 < p.z < 1.45:
            return True
    for nm_ in ('cheek_R', 'cheek_L'):
        if (p - V(T[nm_]['pos'])).length < 0.55:
            return True
    if S.NOSE1817:     # 1.8.17: no stringer / frame across the new nose windows, the K-5 frames, the astrodome or the keel fairing's opening
        for w in S.NOSE1817_WINDOWS:
            if w['kind'] == 'side':
                y0, y1, z0, z1 = w['rect']
                if y0 - 0.10 < y < y1 + 0.10 and z0 - 0.10 < p.z < z1 + 0.10 and p.x * w['side'] > 0.3:
                    return True
            elif w['kind'] == 'top':
                y0, y1, x0, x1 = w['rect']
                if y0 - 0.10 < y < y1 + 0.10 and x0 - 0.10 < p.x < x1 + 0.10 and p.z > 0.9:
                    return True
            elif w['kind'] == 'dome':
                if dome and math.hypot(p.x, y - w['cy']) < w['r'] + 0.12 and p.z > 0.9:
                    return True
        for k5 in S.NOSE1817_K5:
            if k5['y_a'] - 0.10 < y < k5['y_f'] + 0.30 and k5['z0'] - k5['drop'] - 0.10 < p.z < k5['z1'] + k5['rise'] + 0.10 and p.x * k5['side'] > 0.3:
                return True
    return False


def _dome_spans(a, b):
    """1.8.18 (S.DOME_RING1818): the parts [t0, t1] of the segment a -> b that lie outside the astrodome's stop circle (plan radius
    r_stop about the dome centre, just under the inner ring's outer edge: frames / stringers end ON the ring). Segments under the nose top
    (z > 0.9) only; [(0, 1)] when the segment does not reach the circle, [] when it lies inside."""
    dome = [w for w in S.NOSE1817_WINDOWS if w['kind'] == 'dome']
    if not dome or min(a.z, b.z) <= 0.9:
        return [(0.0, 1.0)]
    cy, R = dome[0]['cy'], S.DOME_RING1818_SECTION['r_stop']
    ax, ay, dx, dy = a.x, a.y - cy, b.x - a.x, b.y - a.y
    A = dx * dx + dy * dy; Bq = 2 * (ax * dx + ay * dy); C = ax * ax + ay * ay - R * R
    disc = Bq * Bq - 4 * A * C
    if A < 1e-12 or disc <= 0:
        return [(0.0, 1.0)]
    sq = math.sqrt(disc)
    t0, t1 = (-Bq - sq) / (2 * A), (-Bq + sq) / (2 * A)       # inside the circle for t0 < t < t1
    if t1 <= 0 or t0 >= 1:
        return [(0.0, 1.0)]
    out = []
    if t0 > 0:
        out.append((0.0, t0))
    if t1 < 1:
        out.append((t1, 1.0))
    return out


def _bar_cap(mb, p, ax, w, h, up, mat='structure'):
    """1.8.18: the end face of a _bar at p (same section frame as _bar), facing along ax."""
    ax = V(ax).normalized(); up = V(up).normalized()
    s = ax.cross(up)
    if s.length < 1e-6:
        s = ax.orthogonal()
    s.normalize(); u = s.cross(ax).normalized()
    oriented_quad(mb, [p + s * (w / 2) + u * (h / 2), p - s * (w / 2) + u * (h / 2), p - s * (w / 2) - u * (h / 2), p + s * (w / 2) - u * (h / 2)], mat, ax)


def fuselage_internals(fus_ring):
    """frames every 0.55 m (Z-section rings, segments that cross an opening dropped) + 16 stringers per part.
    1.7.8: rings with the skin's own point count and stringer points at the skin's station spacing - the fin-root pinch makes the
    tail section concave at the shoulders, where a coarser ring's chords (28 points) and 0.55 m stringer segments ran outside the
    skin (structure flecks on the tail in the 1.7.8 r78 renders)."""
    NR = S.FUS_N
    out = {}
    y = S.FUS[0][0] - 0.30
    ys = []
    while y > S.FUS[-1][0] + 0.25:
        ys.append(y); y -= FRAME_STEP
    for y in ys:
        part = _fus_part_of(y)
        if part is None or any(abs(y - sp) < 0.16 for sp in S.SPLITS):
            continue
        mb = out.setdefault(part, MeshBuf())
        top, bot, hw, n = S.fus_station(y)
        ctr = V((0, y, (top + bot) / 2))
        r0 = fus_ring(y, 0.014, NR); r1 = fus_ring(y, 0.075, NR)
        # 1.8.18: a frame that runs under the astrodome is clipped on its inner ring (closed ends); the others keep the 1.8.17 rule
        ring18 = getattr(S, 'DOME_RING1818', False) and any(_dome_spans(r0[k], r0[(k + 1) % NR]) != [(0.0, 1.0)] for k in range(NR))
        for k in range(NR):
            k1 = (k + 1) % NR
            mid = (r0[k] + r0[k1]) / 2
            spans = _dome_spans(r0[k], r0[k1]) if ring18 else [(0.0, 1.0)]
            if not spans or _fus_excluded(mid, y, dome=not ring18) or S.in_pinch(r0[k]) or S.in_pinch(r0[k1]):
                continue
            off = V((0, 0.007, 0))
            for t0, t1 in spans:       # (one full span unless the segment reaches the astrodome ring)
                lp = lambda p, q, t: p if t == 0.0 else (q if t == 1.0 else p.lerp(q, t))      # exact end points when not clipped
                a, b = lp(r0[k], r0[k1], t0), lp(r0[k], r0[k1], t1)
                d, c_ = lp(r1[k], r1[k1], t0), lp(r1[k], r1[k1], t1)
                oriented_quad(mb, [a + off, b + off, c_ + off, d + off], 'structure', V((0, 1, 0)))
                oriented_quad(mb, [a - off, b - off, c_ - off, d - off], 'structure', V((0, -1, 0)))
                oriented_quad(mb, [d + off, c_ + off, c_ - off, d - off], 'structure', ctr - (c_ + d) / 2)
                oriented_quad(mb, [d + off * 3, c_ + off * 3, c_ + off, d + off], 'structure', ctr - (c_ + d) / 2)    # inner flange
                for t_, p_, q_, sg in ((t0, a, d, -1), (t1, b, c_, 1)):     # 1.8.18: closed end where the frame stops on the dome ring
                    if 0.0 < t_ < 1.0:
                        oriented_quad(mb, [p_ + off, p_ - off, q_ - off, q_ + off], 'structure', (r0[k1] - r0[k]) * sg)
    NSTR = 16
    bounds = [S.FUS[0][0]] + S.SPLITS + [S.FUS[-1][0]]
    for i, part in enumerate(S.FUS_PARTS):
        y0, y1 = bounds[i] - 0.06, bounds[i + 1] + 0.06
        n = max(1, int(math.ceil((y0 - y1) / 0.28)))
        sy = [y0 + (y1 - y0) * k / n for k in range(n + 1)]
        mb = out.setdefault(part, MeshBuf())
        for j in range(NSTR):
            jj = int(round((j + 0.5) * NR / NSTR)) % NR
            pts = [fus_ring(y, 0.027, NR)[jj] for y in sy]
            # 1.8.18: a stringer that runs under the astrodome is clipped on its inner ring (closed ends); the others keep the 1.8.17 rule
            ring18 = getattr(S, 'DOME_RING1818', False) and any(_dome_spans(a, b) != [(0.0, 1.0)] for a, b in zip(pts, pts[1:]))
            for k_, (a, b) in enumerate(zip(pts, pts[1:])):
                m = (a + b) / 2
                spans = _dome_spans(a, b) if ring18 else [(0.0, 1.0)]
                if (not spans or _fus_excluded(m, m.y, dome=not ring18) or _fus_excluded(a, a.y, dome=not ring18) or _fus_excluded(b, b.y, dome=not ring18)
                        or S.in_pinch(a) or S.in_pinch(b)):
                    continue
                top, bot, hw, n_ = S.fus_station(m.y)
                inward = (V((0, m.y, (top + bot) / 2)) - m).normalized()
                w_, h_ = 0.022 + 0.006 * (k_ % 2), 0.026 + 0.004 * (k_ % 2)
                for t0, t1 in spans:       # (one full span unless the segment reaches the astrodome ring)
                    a_, b_ = (a if t0 == 0.0 else a.lerp(b, t0)), (b if t1 == 1.0 else a.lerp(b, t1))
                    _bar(mb, a_, b_, w_, h_, inward)     # outer face 12-14 mm in: 6-8 mm off the inner skin
                    for t_, p_, sg in ((t0, a_, -1), (t1, b_, 1)):     # 1.8.18: closed end where the stringer stops on the dome ring
                        if 0.0 < t_ < 1.0:
                            _bar_cap(mb, p_, (b - a) * sg, w_, h_, inward)
    return out


def bay_internals():
    """bomb-bay roof beams (transverse every 0.5 m + 2 longitudinal) and wall rack frames (clear of every stock store envelope)."""
    mb = MeshBuf()
    y0, y1 = S.BAY_Y
    zr = S.BAY_ROOF_Z - 0.032
    x = S.BAY_HALF_W - 0.06
    k = int((y1 - y0) / 0.5)
    for i in range(k + 1):
        yy = y0 + 0.08 + (y1 - y0 - 0.16) * i / k
        _bar(mb, V((-x, yy, zr)), V((x, yy, zr)), 0.05, 0.06, V((0, 0, 1)))     # 6 cm deep, top 2 mm under the roof
    ys_ = [y0 + 0.08 + (y1 - y0 - 0.16) * i / k for i in range(k + 1)]
    for sx in (-0.45, 0.45):      # longitudinal roof beams in bays between the transverse beams (one bar per bay)
        for ya, yb in zip(ys_, ys_[1:]):
            _bar(mb, V((sx, ya, zr - 0.05)), V((sx, yb, zr - 0.05)), 0.05, 0.04, V((0, 0, 1)))
    for i in range(k + 1):          # rack uprights on the walls with diagonal bracing
        yy = y0 + 0.08 + (y1 - y0 - 0.16) * i / k
        for sxx in (-1, 1):
            _bar(mb, V((sxx * (x + 0.024), yy, -0.15)), V((sxx * (x + 0.024), yy, zr)), 0.035, 0.035, V((sxx, 0, 0)))
            if i < k:
                yb = y0 + 0.08 + (y1 - y0 - 0.16) * (i + 1) / k
                _bar(mb, V((sxx * (x + 0.024), yy, -0.10)), V((sxx * (x + 0.024), yb, zr - 0.05)), 0.025, 0.02, V((sxx, 0, 0)))
    return mb


def engine_internals(kind, side, nac_profile):
    """behind the cowl (the fal R-1820 face is the 9-cylinder single row + nose case): mount ring + 8 tubular struts to the crankcase,
    and on the outboard engines the accessory section (case, 2 magnetos, carburettor, supercharger housing). The inboard engines'
    accessory space is the gear well (the wheel stows there) - only the mount ring above the well. Returns (engine mb, nacelle mb)."""
    xa, za, ylip, yprop, R, yend, zb = S.NACELLES[kind]
    ax = V((xa * side, 0, za))
    e, nmb = MeshBuf(), MeshBuf()
    yfw = 3.735 if kind == 'inner' else ylip - 1.05      # firewall (inboard: just ahead of the wheel well, y 1.12..3.72)
    yring = yfw + 0.03
    ring = circle_pts(V((xa * side, yring, za)), V((0, 1, 0)), 0.42, 16)
    ring_c = V((xa * side, yring, za))
    for a, b in zip(ring, ring[1:] + ring[:1]):       # (inboard: the firewall stands 1 cm ahead of the wheel well front wall)
        _bar(e, a, b, 0.035, 0.035, (a - ring_c), 'engine')
    crank = circle_pts(V((xa * side, ylip - 0.55, za)), V((0, 1, 0)), 0.30, 8)
    for k in range(8):
        a, b = ring[2 * k], crank[k]
        _bar(e, a, b, 0.03, 0.03, V((0, 0, 1)), 'engine')
    if kind == 'outer':
        y0 = ylip - 0.56
        cylinder(e, V((xa * side, y0, za)), V((xa * side, y0 - 0.22, za)), 0.33, 0.30, N=20, mat='engine')     # supercharger / blower case
        cylinder(e, V((xa * side, y0 - 0.22, za)), V((xa * side, y0 - 0.38, za)), 0.24, 0.22, N=16, mat='metal_dark')   # accessory case
        for sx in (-1, 1):
            cylinder(e, V((xa * side + sx * 0.13, y0 - 0.38, za + 0.10)), V((xa * side + sx * 0.13, y0 - 0.52, za + 0.10)), 0.055, N=10, mat='metal_dark')   # magnetos
        box(e, (xa * side, y0 - 0.33, za - 0.30), (0.20, 0.16, 0.14), 'engine')            # carburettor (updraft)
        cylinder(e, V((xa * side, y0 - 0.33, za - 0.22)), V((xa * side, y0 - 0.33, za - 0.05)), 0.05, N=10, mat='engine')
    # firewall (nacelle) - a disc with the mount pads, inside the nacelle section
    rs, top, bot = nac_profile(kind, yfw)
    cz = (top + bot) / 2
    fi = 0.045 if S.NAC183 else 0.02          # 1.8.3: inside the dark band under the cowl flaps (3.5 cm in)
    fw = [V((xa * side + (rs - fi) * math.cos(2 * math.pi * k / 24), yfw, cz + ((top - bot) / 2 - fi) * math.sin(2 * math.pi * k / 24))) for k in range(24)]
    fc = sum(fw, V()) / len(fw)
    fan_cap(nmb, fw, fc, 'structure', V((0, 1, 0)))
    fan_cap(nmb, [p - V((0, 0.006, 0)) for p in fw], fc - V((0, 0.006, 0)), 'structure', V((0, -1, 0)))
    # oil tank (37 US gal) behind the firewall, above the wheel well on the inboard engines
    yo = yfw - 0.32
    zo = 0.52 if kind == 'inner' else za + 0.12
    cylinder(nmb, V((xa * side - 0.28, yo, zo)), V((xa * side + 0.28, yo, zo)), 0.12, N=14, mat='metal_dark')
    return e, nmb


def turbo(kind, side, nac_profile):
    """GE B-22 turbo-supercharger in the nacelle floor aft of the wheel well (ref: a round disc under each nacelle): turbine housing
    flush with the skin (bucket-wheel cooling cap below), nozzle-box ring, exhaust hood aft, the exhaust pipe from the collector
    along the nacelle floor and the intercooler duct up to the carburettor (inside). Returns (mb, exhaust exit point)."""
    xa, za, ylip, yprop, R, yend, zb = S.NACELLES[kind]
    ty = 0.0 if kind == 'inner' else -0.20      # (in the engine part, as the 1.7 turbo: keeps the engine collider / CoM within ~0.3 m)
    rs, top, bot = nac_profile(kind, ty)
    x = xa * side
    zs = bot + 0.004
    c = V((x, ty, zs))
    mb = MeshBuf()
    up = V((0, 0, 1))
    cylinder(mb, c + up * 0.14, c - up * 0.035, 0.235, 0.235, N=28, mat='exhaust', cap0=False)                 # turbine housing
    ring_o = circle_pts(c - up * 0.035, up, 0.235, 28); ring_i = circle_pts(c - up * 0.045, up, 0.17, 28)
    loft(mb, [ring_o, ring_i], 'exhaust')                                                                        # nozzle box lip
    cylinder(mb, c - up * 0.045, c - up * 0.075, 0.17, 0.10, N=24, mat='metal_dark')                            # bucket wheel + cap
    cylinder(mb, c - up * 0.075, c - up * 0.09, 0.10, 0.05, N=16, mat='exhaust')
    # exhaust hood: a half tube from the housing aft (waste gate exit), its mouth = the IR source
    for k in range(6):
        a0 = math.pi * k / 6; a1 = math.pi * (k + 1) / 6
        def pt(y, a, r):
            return V((x + r * math.cos(a), y, zs - 0.02 - r * math.sin(a)))
        q = [pt(ty - 0.20, a0, 0.09), pt(ty - 0.20, a1, 0.09), pt(ty - 0.55, a1, 0.075), pt(ty - 0.55, a0, 0.075)]
        oriented_quad(mb, q, 'exhaust', V((math.cos((a0 + a1) / 2), 0, -math.sin((a0 + a1) / 2))))
        oriented_quad(mb, [p_ + V((0, 0, 0.004)) for p_ in q], 'metal_dark', V((-math.cos((a0 + a1) / 2), 0, math.sin((a0 + a1) / 2))))
    # inside: exhaust pipe from the collector ring forward-down to the turbo, intercooler duct up to the carburettor
    if kind == 'inner':          # inboard engines: the pipe runs outboard of the wheel well (x 2.92..3.52) and the trunnion
        p1 = V((x + side * 0.56, ylip - 0.30, za - 0.30)); p2 = V((x + side * 0.56, 0.95, za - 0.30))
        cylinder(mb, p1, p2, 0.075, N=10, mat='exhaust')
        cylinder(mb, p2, c + V((side * 0.18, 0.10, 0.10)), 0.075, N=10, mat='exhaust')
    else:
        cylinder(mb, V((x + side * 0.30, ylip - 0.30, za - 0.40)), c + V((side * 0.18, 0.10, 0.10)), 0.075, N=10, mat='exhaust')
    if kind == 'inner':
        q1 = V((x - side * 0.40, 0.95, za - 0.20))
        cylinder(mb, c + V((-side * 0.15, 0.05, 0.12)), q1, 0.07, N=10, mat='metal_dark')
        cylinder(mb, q1, V((x - side * 0.40, 3.70, za + 0.0)), 0.07, N=10, mat='metal_dark')
    else:
        cylinder(mb, c + V((-side * 0.15, 0.05, 0.12)), V((x - side * 0.10, ylip - 0.75, za - 0.20)), 0.07, N=10, mat='metal_dark')
    return mb, V((x, ty - 0.55, zs - 0.06))


def le_intakes(side, wing_station):
    """oil-cooler and intercooler intakes in the wing leading edge beside each nacelle (real B-17G; the reference has them): a dark
    mouth band just ahead of the LE with framed lips. Returns {part: mb}."""
    out = {}
    for x0, x1 in ((1.62, 2.12), (3.98, 4.52), (5.30, 5.78), (7.42, 7.92)):
        part = next(nm for nm, a, b in _wing_parts_x(side) if a <= (x0 + x1) / 2 < b)
        mb = out.setdefault(part, MeshBuf())
        xs = [x0 + (x1 - x0) * k / 6 for k in range(7)]
        top, bot = [], []
        for x in xs:
            st = wing_station(x, side)
            le = st.point(0.0, True)
            fwd = -st.cdir
            top.append(st.point(0.012, True) + fwd * 0.004); bot.append(st.point(0.012, False) + fwd * 0.004)
        for a0, a1, b0, b1 in zip(top, top[1:], bot, bot[1:]):
            mid = (a0 + a1 + b0 + b1) / 4
            oriented_quad(mb, [a0, a1, b1, b0], 'metal_dark', V((0, 1, 0)))
        for line in (top, bot):
            frame_poly(mb, line, sum(line, V()) / len(line) + V((0, -0.5, 0)), 0.014, 0.010, 0.002)
        for p0, p1 in ((top[0], bot[0]), (top[-1], bot[-1])):
            NS.sec_tube(mb, p0, p1, 0.014, 0.010, V((0, 1, 0)), mat='paint')
    return out


def add_internals(parts):
    """append the internals to the parts' meshes (world space, rest pose) and move the IR sources to the turbo exhausts."""
    import b17g_parts as P
    by = {p.name: p for p in parts}
    stats = {}
    def put(name, mb):
        p = by.get(name)
        if p is None or p.mesh is None or not mb.faces:
            return
        p.mesh.extend(mb); stats[name] = stats.get(name, 0) + mb.tri_count()
    for side in (-1, 1):
        for name, mb in wing_internals(side, P.wing_station).items():
            put(name, mb)
        if not S.NAC183:
            for name, mb in le_intakes(side, P.wing_station).items():
                put(name, mb)
        for kind in ('inner', 'outer'):
            num = S.ENGINE_NUM[(side, kind)]
            e, n = engine_internals(kind, side, P.nac_profile)
            put(f'engine_{num}', e); put(f'nacelle_{num}', n)
            if S.NAC183:      # 1.8.3 turbo / exhaust (b17g_nacelle); the 1.8.2 turbo stays only as the collider source of the engine part
                import b17g_nacelle as N
                t, exit_ = N.turbo(kind, side)
                hm = turbo(kind, side, P.nac_profile_v182)[0]
                if S.NAC188:      # 1.8.8: + the 1.8.7 turbo (the belly it sits on moved up): the engine collider AABB stays the 1.8.7 one
                    N._USE188 = False
                    try:
                        hm.extend(N.turbo(kind, side)[0])
                    finally:
                        N._USE188 = True
                hs = Part(f'engine_{num}_hullsrc', f'engine_{num}', mesh=hm,
                          info={'kind': 'hull_src', 'note': 'collider source only (1.8.2 turbo): Unity bakes it into the engine collider, then deletes it'})
                parts.append(hs); by[hs.name] = hs
            else:
                t, exit_ = turbo(kind, side, P.nac_profile)
            put(f'engine_{num}', t)
            if f'exhaust_{num}' in by:
                by[f'exhaust_{num}'].pivot = exit_
    if S.NAC183:
        import b17g_nacelle as N
        for name, n_ in N.le_intakes(parts, P.wing_station).items():
            stats[name] = stats.get(name, 0) + n_
    for name, mb in fuselage_internals(P.fus_ring).items():
        put(name, mb)
    put('B17G', bay_internals())
    # nose compartment floor over the chin turret (the bombardier / navigator sit on it; without it the Unity crew check's down-rays
    # left through the 3 cm gap between the chin race and the ring liner)
    nf = MeshBuf()
    ys = [5.06 + (6.74 - 5.06) * k / 12 for k in range(13)]
    zf = 0.16 if S.ANM2_SLOTS else 0.26      # round 6: 4 cm lower (the dead-pose hands reached 0.287); 1.8.13 r3/r4: 10 cm more (cheek AN/M2 grips at +20 deg)
    for ya, yb in zip(ys, ys[1:]):
        wa, wb = P.fus_skin_x(ya, zf, 0.02), P.fus_skin_x(yb, zf, 0.02)
        if wa < 0.05 or wb < 0.05:
            continue
        q = [V((-wa, ya, zf)), V((wa, ya, zf)), V((wb, yb, zf)), V((-wb, yb, zf))]
        oriented_quad(nf, q, 'interior', V((0, 0, 1)))
        oriented_quad(nf, [p + V((0, 0, -0.006)) for p in q], 'interior', V((0, 0, -1)))
    put('fus_nose', nf)
    return stats


def round_hole(mb, c, r_drop, near, z_min=-9.0, n=5, z_max=9.0):
    """cut a round hole about the vertical axis through c: faces with a corner within `near` (xy) are split n x n (triangles: n^2
    barycentric pieces, quads: n x n bilinear) and the pieces whose centre is within r_drop are dropped (UVs interpolated)."""
    out = []
    def rr(p):
        return math.hypot(p.x - c.x, p.y - c.y)
    # 1.7.8 (in game 1.7.7: stepped lighter rectangles on the roof aft of the top turret): every piece had its own corners, so each
    # piece shaded with its own flat normal while the skin around it is smooth - the split faces showed as a lighter staircase.
    # Pieces now share vertices with each other and with the uncut skin (weld by position), as tail_cut does since round 6.
    key = {}
    for f in mb.faces:
        for i in f['idx']:
            p = mb.verts[i]; key.setdefault((round(p.x, 6), round(p.y, 6), round(p.z, 6)), i)
    # and the new points go ON the fuselage section (superellipse), not on the flat parent face: bilinear pieces of one parent face all
    # got that face's flat normal, so the split region still shaded as flat rectangles inside the smooth skin (diag render r178)
    def on_skin(p):
        top, bot, hw, n_ = S.fus_station(p.y)
        cz, hz = (top + bot) / 2, (top - bot) / 2
        dx, dz = p.x, p.z - cz
        f_ = (abs(dx / hw) ** n_ + abs(dz / hz) ** n_)
        if f_ < 1e-9:
            return p
        k_ = f_ ** (-1.0 / n_)
        return V((S.fus_pinch(p.y, dx * k_, cz + dz * k_), p.y, cz + dz * k_))
    def vid(p, edge):        # points on the parent face's edges stay on that (flat) edge: no crack against an unsplit neighbour
        k = (round(p.x, 6), round(p.y, 6), round(p.z, 6))
        if k not in key:
            key[k] = mb.v(p if edge else on_skin(p))
        return key[k]
    for f in mb.faces:
        P_ = [mb.verts[k] for k in f['idx']]
        if not (any(rr(p) < near for p in P_) and min(p.z for p in P_) > z_min and max(p.z for p in P_) < z_max) or len(P_) not in (3, 4):
            out.append(f); continue
        # 1.7.8: only faces the opening actually crosses are split (the 1.7.7 split every face within `near`, a wide faceted patch)
        def seg_d(a, b):
            ax_, ay_, bx_, by_ = a.x - c.x, a.y - c.y, b.x - c.x, b.y - c.y
            dx_, dy_ = bx_ - ax_, by_ - ay_
            t_ = max(0.0, min(1.0, -(ax_ * dx_ + ay_ * dy_) / max(dx_ * dx_ + dy_ * dy_, 1e-12)))
            return math.hypot(ax_ + dx_ * t_, ay_ + dy_ * t_)
        inside = (lambda q: all(((P_[(k + 1) % len(P_)].x - P_[k].x) * (q[1] - P_[k].y) - (P_[(k + 1) % len(P_)].y - P_[k].y) * (q[0] - P_[k].x)) >= 0 for k in range(len(P_)))
                  or all(((P_[(k + 1) % len(P_)].x - P_[k].x) * (q[1] - P_[k].y) - (P_[(k + 1) % len(P_)].y - P_[k].y) * (q[0] - P_[k].x)) <= 0 for k in range(len(P_))))
        if min(seg_d(P_[k], P_[(k + 1) % len(P_)]) for k in range(len(P_))) > r_drop + 0.01 and not inside((c.x, c.y)):
            out.append(f); continue
        U = f['uv']
        pieces = []
        if len(P_) == 3:
            def bp(i, j):
                a, b = i / n, j / n
                w = (1 - a - b, a, b)
                p = P_[0] * w[0] + P_[1] * w[1] + P_[2] * w[2]
                u = None if U is None else (U[0][0] * w[0] + U[1][0] * w[1] + U[2][0] * w[2], U[0][1] * w[0] + U[1][1] * w[1] + U[2][1] * w[2])
                return p, u, (i == 0 or j == 0 or i + j == n)
            for i in range(n):
                for j in range(n - i):
                    pieces.append([bp(i, j), bp(i + 1, j), bp(i, j + 1)])
                    if i + j + 1 < n:
                        pieces.append([bp(i + 1, j), bp(i + 1, j + 1), bp(i, j + 1)])
        else:
            def qp(i, j):
                a, b = i / n, j / n
                p = (P_[0] * (1 - a) + P_[1] * a) * (1 - b) + (P_[3] * (1 - a) + P_[2] * a) * b
                u = None if U is None else tuple((U[0][k] * (1 - a) + U[1][k] * a) * (1 - b) + (U[3][k] * (1 - a) + U[2][k] * a) * b for k in (0, 1))
                return p, u, (i in (0, n) or j in (0, n))
            for i in range(n):
                for j in range(n):
                    pieces.append([qp(i, j), qp(i + 1, j), qp(i + 1, j + 1), qp(i, j + 1)])
        for pc in pieces:
            cen = sum((p for p, u, e in pc), V()) / len(pc)
            if rr(cen) < r_drop:
                continue
            idx = [vid(p, e) for p, u, e in pc]
            out.append(dict(idx=idx, mat=f['mat'], uv=None if U is None else [u for p, u, e in pc], smooth=f['smooth']))
    mb.faces = out
