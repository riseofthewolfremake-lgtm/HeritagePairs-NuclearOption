"""MSB-17 1.9.12: upper-wing spoiler panels (visible airbrake panels) and the eight green formation-light strips.

Both are thin plates on the UNCUT skin (the owning part's mesh, collider source and livery-atlas UV stay exactly as in 1.9.11): the plate
is the skin itself, cut to the plate's outline and lifted along the skin normals ("decal": every skin triangle inside the outline is
clipped by the outline planes, so the plate has a vertex wherever the faceted skin has one - it lies on the skin's own stations, ring
points and creases by construction, check_light-strips.md Missing 2 / 3, check_airbrake-panels.md Missing "proud plate must follow the
faceted wing skin"). Every piece is a CLOSED slab (model check c winding).

  spoilers (M.SPOILERS1912): six panels (round 2; the first build had four small ones), wing_inner / wing_mid upper surface ahead of the
      flap cove, hinge at the front edge.
      airbrake_<in|mid|out>_<L|R>_hinge  empty at the hinge-line midpoint, local +X = hinge axis (+x on both sides), +Z = skin normal, +Y forward
      airbrake_<in|mid|out>_<L|R>        the panel under the hinge: top face `paint` carrying the atlas UV of the skin under it (so it wears
                                         the livery of the skin it covers and the livery atlas does not change), underside `cove` (round 3:
                                         the near-black finish of the bed, was `interior`) with chordwise stiffeners `gear`, edges `cove`,
                                         two or three hinge arms `gear` that stand in the wing
                                         when shut and swing out with the panel
      airbrake_<in|mid|out>_<L|R>_bed    bed on the wing (child of the wing part), 10 mm larger all round: a near-black plate `cove` (the
                                         seam line when shut) carrying a frame, ribs and a stringer `gear` (a recess with structure when open)
      No collider, no part: Unity's stock Airbrake rotates the hinge transforms about their local X.
  strips (M.STRIPS1912): slimelight_<fwd|aft|fin|tip>_<L|R>, material `light_off` (Unity: stock light_green_off, lit by NavLights with
      the stock slimelight_on), children of fus_cockpit / fus_waist / fin / wing_tip_<s>.

build(parts) is called by build_msb1780.py AFTER B.pack_livery (the panels read the packed UV of the wing skin and are not packed).
"""
import math
from mathutils import Vector as V
import b17g_spec as S
import msb_spec as M
import b17g_parts as P
from b25h_parts import Part
from b25h_geom import MeshBuf, oriented_quad, frame_from_axes

PREFIXES = ('airbrake_', 'slimelight_')     # object names of this module (build: left out of the z-fix pass; check: row z instead of row m)
WELD = 5            # decimals for welding clipped points (0.01 mm)
MIN_AREA = 2e-6     # m2: clipped slivers below this are dropped (Unity drops degenerate triangles: triangle parity check)


# ---------------------------------------------------------------------------------------------- decal of a skin
def _triangulate(pts):
    """corner-index triangles of one face exactly as the exporter cuts it (blender/b17g/export_b17g.py: bmesh.ops.triangulate with its
    defaults on every mesh before the FBX is written). The skin quads of a tapered, twisted surface are not flat: a plate cut along the
    other diagonal stands up to several mm off the triangles the game draws (first 1.9.12 build: the z-fight pass found fin-strip faces
    inside 0.8 mm of the fin skin)."""
    if len(pts) == 3:
        return [(0, 1, 2)]
    import bmesh
    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in pts]
    bm.verts.index_update()
    bm.faces.new(vs)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    out = [tuple(v.index for v in f.verts) for f in bm.faces]
    bm.free()
    return out


def _tris(mb, pred):
    """triangles (points, packed uv or None) of the faces of mb accepted by pred(face, centre, normal), cut as the exporter cuts them."""
    for f in mb.faces:
        pts = [mb.verts[i] for i in f['idx']]
        n = V()
        for k in range(1, len(pts) - 1):
            n += (pts[k] - pts[0]).cross(pts[k + 1] - pts[0])
        if n.length < 1e-12:
            continue
        c = sum(pts, V()) / len(pts)
        if not pred(f, c, n.normalized()):
            continue
        uv = f.get('uv_packed')
        for t in _triangulate(pts):
            tp = [pts[k] for k in t]
            if (tp[1] - tp[0]).cross(tp[2] - tp[0]).dot(n) < 0:      # keep the face's winding
                t = (t[0], t[2], t[1]); tp = [pts[k] for k in t]
            yield tp, ([uv[k] for k in t] if uv else None)


def _clip(pts, uvs, n, d):
    """Sutherland-Hodgman: keep the part of the convex polygon with n . p <= d (uv interpolated along the cut edges)."""
    out_p, out_u = [], []
    m = len(pts)
    for i in range(m):
        a, b = pts[i], pts[(i + 1) % m]
        da, db = n.dot(a) - d, n.dot(b) - d
        if da <= 0:
            out_p.append(a)
            if uvs:
                out_u.append(uvs[i])
        if (da < 0 < db) or (db < 0 < da):
            t = da / (da - db)
            out_p.append(a + (b - a) * t)
            if uvs:
                ua, ub = uvs[i], uvs[(i + 1) % m]
                out_u.append((ua[0] + (ub[0] - ua[0]) * t, ua[1] + (ub[1] - ua[1]) * t))
    return out_p, (out_u if uvs else None)


def _area(pts):
    return sum(((pts[k] - pts[0]).cross(pts[k + 1] - pts[0])).length for k in range(1, len(pts) - 1)) / 2


def decal(mb, pred, planes):
    """the skin faces of mb accepted by pred, cut to the convex outline `planes` [(normal, d)]: keep n . p <= d.
    -> dict(verts=[V], normals=[V] (area-weighted vertex normals of the cut skin), polys=[(vertex ids, uv list or None)], area, dropped)"""
    verts, index, polys, dropped, area = [], {}, [], 0, 0.0
    for pts, uvs in _tris(mb, pred):
        for n, d in planes:
            pts, uvs = _clip(pts, uvs, n, d)
            if len(pts) < 3:
                break
        if len(pts) < 3:
            continue
        ids, uu = [], []
        for k, p in enumerate(pts):
            key = (round(p.x, WELD), round(p.y, WELD), round(p.z, WELD))
            if key not in index:
                index[key] = len(verts); verts.append(V(p))
            i = index[key]
            if ids and (i == ids[-1] or i == ids[0] and k == len(pts) - 1):
                continue
            ids.append(i)
            if uvs:
                uu.append(uvs[k])
        if len(ids) < 3 or _area([verts[i] for i in ids]) < MIN_AREA:
            dropped += 1
            continue
        area += _area([verts[i] for i in ids])
        polys.append((ids, uu if uvs else None))
    normals = [V() for _ in verts]
    for ids, _ in polys:
        pp = [verts[i] for i in ids]
        n = V()
        for k in range(1, len(pp) - 1):
            n += (pp[k] - pp[0]).cross(pp[k + 1] - pp[0])
        for i in ids:
            normals[i] += n
    normals = [n.normalized() if n.length > 1e-12 else V((0, 0, 1)) for n in normals]
    return dict(verts=verts, normals=normals, polys=polys, area=area, dropped=dropped)


def slab(mb, dc, h_front, h_back, mat_front, mat_back, mat_edge, smooth_front=False):
    """closed slab on a decal: front face at h_front along the skin normals, back face at h_back (reversed), skirts on the open boundary.
    A `paint` front face keeps the packed atlas UV of the skin under it. -> boundary edge count"""
    vf = [mb.v(p + n * h_front) for p, n in zip(dc['verts'], dc['normals'])]
    vb = [mb.v(p + n * h_back) for p, n in zip(dc['verts'], dc['normals'])]
    edges = {}
    for ids, uu in dc['polys']:
        if mat_front == 'paint':
            if not uu:
                raise SystemExit('[1912] a paint plate needs the packed UV of the skin under it (call after pack_livery)')
            mb.face([vf[i] for i in ids], 'paint', list(uu), smooth_front)
            mb.faces[-1]['uv_packed'] = list(uu)
        else:
            mb.face([vf[i] for i in ids], mat_front, None, smooth_front)
        mb.face([vb[i] for i in reversed(ids)], mat_back, None, False)
        for a, b in zip(ids, ids[1:] + ids[:1]):
            edges[(a, b)] = edges.get((a, b), 0) + 1
    nb = 0
    for (a, b), c in edges.items():
        if (b, a) in edges:
            continue
        nb += 1
        mb.face([vf[b], vf[a], vb[a], vb[b]], mat_edge, None, False)     # the outside of a boundary edge of an outward-wound face
    return nb


# ---------------------------------------------------------------------------------------------- spoilers
S_FRONT = M.SPOILER_S_FRONT       # hinge line chord fraction (round 2: 0.52; the first build used the ring row 0.5714)


def spoiler_sites():
    """[(name, side, wing part, x0, x1)] in |x|"""
    out = []
    for side in (-1, 1):
        s = 'L' if side < 0 else 'R'
        for key in ('in', 'mid', 'out'):
            x0, x1 = M.SPOILER_X[key]
            out.append((f'airbrake_{key}_{s}', side, M.SPOILER_PART[key] + s, x0, x1))
    return out


def _spoiler_frame(side, x0, x1):
    """corner points on the wing's upper surface (front a / b at |x| x0 / x1, rear a / b), hinge axis (+x), normal, forward."""
    sa, sb = P.wing_station(x0, side), P.wing_station(x1, side)
    fa, fb = sa.point(S_FRONT, True), sb.point(S_FRONT, True)
    ra, rb = sa.point(M.SPOILER_S_REAR, True), sb.point(M.SPOILER_S_REAR, True)
    ax = (fb - fa).normalized()
    if ax.x < 0:
        ax = -ax
    n = ax.cross(((ra + rb) - (fa + fb)) / 2)
    n = n.normalized() if n.z > 0 else (-n).normalized()
    fwd = n.cross(ax).normalized()          # +y (nose) side of the hinge line, in the skin plane
    if fwd.y < 0:
        fwd = -fwd
    return fa, fb, ra, rb, ax, n, fwd


def _edges(side, x0, x1):
    """the panel outline as half-space constants (px, fwd, F, rear, R): x0 <= px . p <= x1, fwd . p <= F (hinge line), rear . p <= R (rear edge)"""
    fa, fb, ra, rb, ax, n, fwd = _spoiler_frame(side, x0, x1)
    rear = n.cross((rb - ra).normalized())
    if rear.y > 0:
        rear = -rear                                   # points aft
    return V((side, 0, 0)), fwd, fwd.dot(fa), rear, rear.dot(ra)


def _outline(side, x0, x1, grow=0.0):
    px, fwd, F, rear, R = _edges(side, x0, x1)
    return [(-px, -(x0 - grow)), (px, x1 + grow), (fwd, F + grow), (rear, R + grow)]


def spoiler_stations(x0, x1):
    """-> (bed rib |x| stations, panel stiffener |x| stations, hinge arm |x| stations). Bed ribs at k / n of the span, stiffeners and arms
    at the half stations between them (shut, a stiffener never stands on a bed rib); arms take the half stations nearest 20 / 80 % (and
    50 % on a panel longer than 1.6 m)."""
    span = x1 - x0
    nb = max(2, int(round(span / M.SPOILER_BAY)))
    ribs = [x0 + span * k / nb for k in range(1, nb)]
    half = [x0 + span * (k + 0.5) / nb for k in range(nb)]
    want = [0.2, 0.8] + ([0.5] if span > 1.6 else [])
    arms = sorted({min(half, key=lambda h: abs((h - x0) / span - t)) for t in want})
    return ribs, [h for h in half if h not in arms], arms


def _bed_members(side, x0, x1, chord):
    """outline planes of the bed's frame, ribs and stringer segments: pieces that TOUCH but never overlap (no coplanar doubles)."""
    px, fwd, F, rear, R = _edges(side, x0, x1)
    fi, w = M.SPOILER_BED_FRAME_IN, M.SPOILER_BEDRIB_W
    xa, xb = x0 + fi, x1 - fi
    ds = M.SPOILER_BED_STRINGER * chord
    span_ = lambda a, b: [(-px, -a), (px, b)]
    out = [span_(xa, xb) + [(fwd, F - fi), (-fwd, -(F - fi - w))],                       # front member
           span_(xa, xb) + [(rear, R - fi), (-rear, -(R - fi - w))]]                     # rear member
    between = [(fwd, F - fi - w), (rear, R - fi - w)]                                    # the field between the two members
    ribs, _, _ = spoiler_stations(x0, x1)
    cols = [(xa, xa + w)] + [(r - w / 2, r + w / 2) for r in ribs] + [(xb - w, xb)]      # side members + ribs, chordwise
    for a, b in cols:
        out.append(span_(a, b) + between)
    for (a0, a1), (b0, b1) in zip(cols, cols[1:]):                                       # stringer segments between the columns
        out.append(span_(a1, b0) + between + [(fwd, F - ds + w / 2), (-fwd, -(F - ds - w / 2))])
    return out


def _panel_stiffeners(side, x0, x1, chord):
    px, fwd, F, rear, R = _edges(side, x0, x1)
    w, ins, sw = M.SPOILER_PRIB_W, M.SPOILER_PRIB_INSET, M.SPOILER_BEDRIB_W
    ds = M.SPOILER_BED_STRINGER * chord
    _, stiff, _ = spoiler_stations(x0, x1)
    out = []
    for xr in stiff:
        col = [(-px, -(xr - w / 2)), (px, xr + w / 2)]
        out.append(col + [(fwd, F - ins), (-fwd, -(F - ds + sw / 2 + 0.010))])           # hinge side of the bed's stringer
        out.append(col + [(fwd, F - ds - sw / 2 - 0.010), (rear, R - ins)])              # rear side
    return out


def build_spoilers(parts):
    by = {p.name: p for p in parts}
    out, info = [], []
    for name, side, wing, x0, x1 in spoiler_sites():
        fa, fb, ra, rb, ax, n, fwd = _spoiler_frame(side, x0, x1)
        skin = by[wing].mesh
        cx = side * (x0 + x1) / 2
        pred = lambda f, c, fn: f['mat'] == 'paint' and 'uv_packed' in f and fn.dot(n) > 0.8 and abs(c.x - cx) < (x1 - x0) / 2 + 0.7
        plate = decal(skin, pred, _outline(side, x0, x1))
        bed = decal(skin, pred, _outline(side, x0, x1, M.SPOILER_RIM))
        want = _area([fa, fb, rb, ra])
        if abs(plate['area'] - want) > 0.02 * want:
            raise SystemExit(f'[1912] {name}: plate area {plate["area"]:.4f} m2, outline {want:.4f} m2 (the decal missed skin faces)')
        chord = ((ra + rb) / 2 - (fa + fb) / 2).length
        mb = MeshBuf()
        # underside (round 3): `cove`, the bed's near-black plate (Unity MSB17_cove), so the opened panel reads dark with the `gear` stiffeners
        # as ribs. Round 2 used `interior`: a 2 m panel-and-frame tile whose slivers showed as blue-violet bands on the 1-2 m panel (renders_r2)
        nb = slab(mb, plate, M.SPOILER_TOP, M.SPOILER_BOTTOM, 'paint', 'cove', 'cove', smooth_front=True)
        # stiffeners under the panel (round 2): closed slabs whose top ends inside the panel's thickness; seen from behind when the panel is open
        n_st = 0
        for planes in _panel_stiffeners(side, x0, x1, chord):
            dc = decal(skin, pred, planes)
            if not dc['polys']:
                raise SystemExit(f'[1912] {name}: an empty panel stiffener')
            slab(mb, dc, M.SPOILER_PRIB_TOP, M.SPOILER_PRIB_BOTTOM, 'gear', 'gear', 'gear'); n_st += 1
        # hinge arms: closed triangular webs fixed to the panel underside; shut they stand inside the wing under the panel,
        # open they swing out of the bed with it (no kinematics)
        piv = (fa + fb) / 2 + n * ((M.SPOILER_TOP + M.SPOILER_BOTTOM) / 2)
        aft = -fwd
        _, _, arms = spoiler_stations(x0, x1)
        for xr in arms:
            h = fa + (fb - fa) * ((xr - x0) / (x1 - x0))
            top = (M.SPOILER_BOTTOM + M.SPOILER_TOP) / 2          # the web's upper edge ends inside the panel's thickness (no top face: it is in the panel)
            a = h + aft * 0.03 + n * top
            b = h + aft * min(0.38, 0.6 * chord) + n * top
            c = h + aft * 0.15 - n * M.SPOILER_ARM_DEPTH
            w = ax * (M.SPOILER_ARM_W / 2)
            tri = [a, b, c]
            oriented_quad(mb, [p + w for p in tri], 'gear', ax)
            oriented_quad(mb, [p - w for p in tri], 'gear', -ax)
            cen = sum(tri, V()) / 3
            for p, q in ((b, c), (c, a)):
                oriented_quad(mb, [p - w, q - w, q + w, p + w], 'gear', (p + q) / 2 - cen)
        frame = frame_from_axes(ax, n)
        # the bed (round 2): a near-black plate (Unity: MSB17_cove, colour 0.05 sRGB, smoothness 0.1) carrying a frame, ribs and a stringer in the
        # plain steel of the landing gear (Unity: MSB17_gear, the uniform msb17_tile_gear_b, metallic 0.6), so the opened bay reads as a recess
        # with structure and not as a flat patch. NOT `well` / `interior` / `cowl`: those tiles are 2 m panel-and-frame pictures (olive fields,
        # blue frames); a 35 mm member shows random slivers of them (seen in the round-2 test render), and `cowl` is as dark as the bed
        mbb = MeshBuf()
        slab(mbb, bed, M.SPOILER_BED_TOP, M.SPOILER_BED_BOTTOM, 'cove', 'cove', 'cove')
        n_bm = 0
        for planes in _bed_members(side, x0, x1, chord):
            dc = decal(skin, pred, planes)
            if not dc['polys']:
                raise SystemExit(f'[1912] {name}: an empty bed member')
            slab(mbb, dc, M.SPOILER_BEDRIB_TOP, M.SPOILER_BEDRIB_BACK, 'gear', 'gear', 'gear'); n_bm += 1
        free = (ra + rb) / 2 + n * M.SPOILER_TOP
        ang = math.radians(M.SPOILER_MAX_ANGLE)
        r = free - piv
        opened = piv + ax * r.dot(ax) + (r - ax * r.dot(ax)) * math.cos(ang) + ax.cross(r) * (-math.sin(ang))   # Blender: open = -angle about +X
        out += [Part(name + '_hinge', wing, pivot=piv, frame=frame, info={'kind': 'airbrake_hinge', 'open_deg': M.SPOILER_MAX_ANGLE, 'hinge_axis': list(ax)}),
                Part(name, name + '_hinge', pivot=piv, frame=frame, mesh=mb, info={'kind': 'airbrake_panel', 'part': wing}),
                Part(name + '_bed', wing, mesh=mbb, info={'kind': 'airbrake_bed', 'part': wing})]
        info.append(dict(name=name, hinge=name + '_hinge', bed=name + '_bed', part=wing, pivot=list(piv), axis=list(ax), up=list(n), fwd=list(fwd),
                         span=(fb - fa).length, chord=chord, area=plate['area'], free_edge=list(free), free_edge_open=list(opened),
                         x=[side * x0, side * x1], s=[S_FRONT, M.SPOILER_S_REAR], arms=len(arms), stiffeners=n_st, bed_members=n_bm))
        print(f'[1912] {name} on {wing}: {(fb - fa).length:.2f} x {chord:.2f} m, {plate["area"]:.3f} m2, {len(plate["polys"])} skin pieces ({plate["dropped"]} slivers dropped), '
              f'{nb} rim edges, {len(arms)} arms, {n_st} stiffener pieces, {n_bm} bed members, free edge z {free.z:.3f} -> {opened.z:.3f} at {M.SPOILER_MAX_ANGLE} deg')
    return out, info


# ---------------------------------------------------------------------------------------------- green strips
def _box(lo, hi):
    """planes of an axis-aligned box given (lo, hi) per axis (None = open)."""
    pl = []
    for ax_ in range(3):
        e = V((0, 0, 0)); e[ax_] = 1.0
        if lo[ax_] is not None:
            pl.append((-e, -lo[ax_]))
        if hi[ax_] is not None:
            pl.append((e, hi[ax_]))
    return pl


def strip_sites():
    """[(name, parent part, face predicate, outline planes, nominal length, nominal width)]"""
    out = []
    for side in (-1, 1):
        s = 'L' if side < 0 else 'R'
        sd = (lambda f, c, fn, side=side: f['mat'] == 'paint' and fn.x * side > 0.30 and c.x * side > 0.05)
        (y1, y0), (z0, z1) = M.STRIP_FWD['y'], M.STRIP_FWD['z']
        out.append((f'slimelight_fwd_{s}', 'fus_cockpit', sd, _box((None, y1, z0), (None, y0, z1)), y0 - y1, z1 - z0))
        (y1, y0), (z0, z1) = M.STRIP_AFT['y'], M.STRIP_AFT['z']
        out.append((f'slimelight_aft_{s}', 'fus_waist', sd, _box((None, y1, z0), (None, y0, z1)), y0 - y1, z1 - z0))
        # fin: a band parallel to the leading edge (the straight run of the LE table), d0..d1 behind it, between two heights
        (z0, z1), (d0, d1) = M.STRIP_FIN['z'], M.STRIP_FIN['behind_le']
        la, lb = V((0, S.interp(S.FIN_LE, z0), z0)), V((0, S.interp(S.FIN_LE, z1), z1))
        e = (lb - la).normalized()
        back = V((0, -1, 0)) - e * V((0, -1, 0)).dot(e)          # in the fin plane, perpendicular to the LE, pointing aft
        back.normalize()
        k = 1.0 / back.dot(V((0, -1, 0)))                         # d is measured along y (behind the LE at the same height)
        fin_sd = (lambda f, c, fn, side=side: f['mat'] == 'paint' and fn.x * side > 0.50)
        out.append((f'slimelight_fin_{s}', 'fin', fin_sd,
                    _box((None, None, z0), (None, None, z1)) + [(-back, -(back.dot(la) + d0 / k)), (back, back.dot(la) + d1 / k)], (lb - la).length, d1 - d0))
        # wing tip: chordwise on the top surface
        (x0, x1), (c0, c1) = M.STRIP_TIP['x'], M.STRIP_TIP['chord']
        st = P.wing_station((x0 + x1) / 2, side)
        ya, yb = st.le.y + st.cdir.y * st.chord * c0, st.le.y + st.cdir.y * st.chord * c1
        tip_sd = (lambda f, c, fn: f['mat'] == 'paint' and fn.z > 0.50)
        lo = (side * x0 if side > 0 else side * x1, yb, None); hi = (side * x1 if side > 0 else side * x0, ya, None)
        out.append((f'slimelight_tip_{s}', f'wing_tip_{s}', tip_sd, _box(lo, hi), ya - yb, x1 - x0))
    return out


def build_strips(parts):
    by = {p.name: p for p in parts}
    out, info = [], []
    for name, parent, pred, planes, length, width in strip_sites():
        dc = decal(by[parent].mesh, pred, planes)
        if dc['area'] < 0.85 * length * width or dc['area'] > 1.25 * length * width:
            raise SystemExit(f'[1912] {name}: strip area {dc["area"]:.4f} m2 against {length:.2f} x {width:.2f} m (the decal missed or doubled skin faces)')
        mb = MeshBuf()
        nb = slab(mb, dc, M.STRIP_LIFT, M.STRIP_BACK, 'light_off', 'light_off', 'light_off')
        c = sum(dc['verts'], V()) / len(dc['verts'])
        n = sum(dc['normals'], V()).normalized()
        out.append(Part(name, parent, mesh=mb, info={'kind': 'formation_light', 'part': parent}))
        info.append(dict(name=name, part=parent, centre=list(c), normal=list(n), length=length, width=width, area=dc['area']))
        print(f'[1912] {name} on {parent}: {length:.2f} x {width:.2f} m, {dc["area"]:.4f} m2, {len(dc["polys"])} skin pieces ({dc["dropped"]} slivers dropped), {nb} rim edges, '
              f'centre {tuple(round(v, 3) for v in c)}, normal {tuple(round(v, 2) for v in n)}')
    return out, info


def build(parts):
    """-> (new parts, contract additions)"""
    out, con = [], {}
    if M.SPOILERS1912:
        ps, info = build_spoilers(parts)
        out += ps
        con['airbrake'] = dict(max_angle=M.SPOILER_MAX_ANGLE, panels=info)
    if M.STRIPS1912:
        ps, info = build_strips(parts)
        out += ps
        con['lights'] = dict(formation=info)
    return out, con
