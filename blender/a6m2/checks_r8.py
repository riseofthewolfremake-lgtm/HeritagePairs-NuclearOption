"""A6M2 r8 model checks (user review 1), run from check_a6m2_model.py on the built .blend:

  tub_rays     cast rays from the pilot eye over the whole forward hemisphere (yaw -90..90, pitch -80..60, 2 deg); the first
               FRONT-facing hit (Unity culls back faces) must be cockpit geometry inside the tub (cockpit_* / gauge_* / ckcanopy_*, or the
               fus_center / wing_C inner skin aft of the bulkhead) or glass (a window). FAIL on: no hit (outside without glass), the engine,
               any exterior part, any outer 'paint' face, or fus_center faces ahead of the bulkhead (the engine / tank bay).
               The exterior canopy is skipped (hidden in the cockpit view; the ck canopy shows).
  frames       every swept canopy member (a6m2_canopy.FRAMES, both sets): rebuilt alone, welded, 0 open boundary edges; every open
               member end lies inside another member (centre-line distance <= half width + 1 mm) or is buried in the fuselage / sill
               (nearest non-frame surface <= 1 mm, or under the skin).
  root_seam    rays from 6 elevations x 12 azimuths at points around the wing-root seam (both sides, y -2.3..+1.0 every 40 mm, the band
               |x| 0.40..0.80, z -0.50..+0.10): FAIL when the first front-facing hit is an inside face ('interior' / 'structure') of
               the fuselage, fillet or wing (light / inside showing through a gap), or when a ray reaches a point inside the fuselage or
               wing (analytic solid) with no front-facing hit before it.
"""
import math, sys
import bpy
from mathutils import Vector as V
from mathutils.bvhtree import BVHTree


class Scene:
    def __init__(self, skip=()):
        Vs, Fs, meta = [], [], []
        for o in bpy.data.objects:
            if o.type != 'MESH' or o.name.startswith(skip):
                continue
            me = o.data
            me.calc_loop_triangles()
            M = o.matrix_world
            b = len(Vs)
            Vs += [M @ v.co for v in me.vertices]
            for lt in me.loop_triangles:
                Fs.append(tuple(i + b for i in lt.vertices))
                meta.append((o.name, me.materials[lt.material_index].name if me.materials else ''))
        self.tree = BVHTree.FromPolygons(Vs, Fs)
        self.meta = meta

    def walk(self, o, d, maxd=50.0):
        """yields (loc, normal, obj, mat, front, dist) along the ray."""
        p = V(o); travelled = 0.0
        for _ in range(64):
            loc, nrm, idx, dist = self.tree.ray_cast(p, d, maxd - travelled)
            if loc is None:
                return
            travelled += dist
            ob, mat = self.meta[idx]
            yield loc, nrm, ob, mat, nrm.dot(d) < 0, travelled
            p = loc + d * 1e-5
            travelled += 1e-5


def tub_rays(R, eye, bulkhead_y):
    sc = Scene(skip=('canopy_windscreen', 'canopy_hood', 'canopy_rear', 'pilot', 'store_', 'cockpit_eye'))
    bad = []
    n = 0
    for el in range(-80, 61, 2):
        for az in range(-90, 91, 2):
            a, e = math.radians(az), math.radians(el)
            d = V((math.sin(a) * math.cos(e), math.cos(a) * math.cos(e), math.sin(e)))
            if d.y <= 0:
                continue
            n += 1
            verdict = 'none'
            for loc, nrm, ob, mat, front, dist in sc.walk(eye, d):
                if mat in ('glass', 'sightglass', 'reticle') or ob.startswith('ckcanopy_'):
                    verdict = 'ok'; break           # glass is double-sided (coincident faces): either facing is the window
                if not front:
                    continue
                if ob.startswith(('cockpit_', 'gauge_', 'ckcanopy_')):
                    verdict = 'ok'; break
                if ob in ('fus_center', 'wing_C') and mat in ('interior', 'structure', 'ck_dark') and loc.y <= bulkhead_y + 0.012:
                    verdict = 'ok'; break
                verdict = f'{ob}/{mat} at ({loc.x:.2f},{loc.y:.2f},{loc.z:.2f})'
                break
            if verdict != 'ok':
                bad.append((az, el, verdict if verdict != 'none' else 'nothing (outside, no glass)'))
    R('tub (r8 review: gaps in the front panel into the engine): rays from the eye over the forward hemisphere (2 deg grid) end on cockpit geometry '
      'inside the tub or on glass; none reaches the engine, an exterior part, an outer skin or the bay ahead of the bulkhead',
      not bad, f'{n} rays, {len(bad)} fail' + (f'; e.g. {bad[:6]}' if bad else ''))
    return bad


def _seg_dist(p, a, b):
    ab = b - a
    t = 0.0 if ab.length < 1e-12 else max(0.0, min(1.0, (p - a).dot(ab) / ab.dot(ab)))
    return (a + ab * t - p).length


def frames(R, CAN, AP, K):
    from b25h_geom import MeshBuf
    open_edges = 0
    bad_joint = []
    sc = Scene(skip=('canopy_', 'ckcanopy_'))          # non-frame surfaces (fuselage, ...)
    members = list(CAN.FRAMES)
    # sill strips of the CK set are part of ckcanopy_fixed; their surfaces count as a burying surface
    CAN.CUR['shape'] = 'ck'
    sill = CAN.ck_sill(CAN.CK) if hasattr(CAN, 'ck_sill') else None
    sill_tree = None
    if sill is not None:
        sill_tree = BVHTree.FromPolygons([V(v) for v in sill.verts], [tuple(f['idx']) for f in sill.faces])
    CAN.CUR['shape'] = 'ext'
    for i, m in enumerate(members):
        CAN.CUR['shape'] = m['set']
        mb = MeshBuf()
        P = [V(p) for p in m['path']]
        nrm = [CAN.out_normal(p) for p in P]
        CAN.sweep(mb, P, nrm, closed=m['closed'])
        CAN.FRAMES.pop()                                 # the re-sweep recorded itself
        key = {}
        ids = []
        for v in mb.verts:
            k_ = (round(v.x, 5), round(v.y, 5), round(v.z, 5))
            ids.append(key.setdefault(k_, len(key)))
        ec = {}
        for f in mb.faces:
            idx = [ids[j] for j in f['idx']]
            for a, b in zip(idx, idx[1:] + idx[:1]):
                if a != b:
                    e = (min(a, b), max(a, b)); ec[e] = ec.get(e, 0) + 1
        open_edges += sum(1 for c in ec.values() if c == 1)
        if m['closed']:
            continue
        hw = (CAN.CK_FRAME[0] if m['set'] == 'ck' else CAN.FW) / 2
        for J in (P[0], P[-1]):
            best = 9.0
            for j, o in enumerate(members):
                if j == i or o['set'] != m['set']:
                    continue
                Q = [V(p) for p in o['path']] + ([V(o['path'][0])] if o['closed'] else [])
                for a, b in zip(Q, Q[1:]):
                    best = min(best, _seg_dist(J, a, b))
            gap = max(0.0, best - hw)
            if gap <= 0.001:
                continue
            near = sc.tree.find_nearest(J)
            dn = near[3] if near[0] is not None else 9.0
            if sill_tree is not None and m['set'] == 'ck':
                ns = sill_tree.find_nearest(J)
                if ns[0] is not None:
                    dn = min(dn, ns[3])
            under = J.z <= AP.body_z_at(abs(J.x), J.y) + 0.001
            if dn <= 0.001 or under:
                continue
            bad_joint.append(f"{m['set']}/{m['part']} member {i} end ({J.x:.3f},{J.y:.3f},{J.z:.3f}) gap {gap * 1000:.1f} mm, surface {dn * 1000:.1f} mm")
    CAN.CUR['shape'] = 'ext'
    R('canopy frames (r8 review: "rectangles glued together"): every member one swept mesh, 0 open boundary edges; every member end inside the member it '
      'meets (gap <= 1 mm) or buried in the fuselage / sill',
      open_edges == 0 and not bad_joint, f'{len(members)} members, open edges {open_edges}, joint gaps {len(bad_joint)}' + (f'; {bad_joint[:6]}' if bad_joint else ''))


def root_seam(R, AP, S, K):
    sc = Scene(skip=('ckcanopy_', 'pilot', 'store_'))
    Vs, Fs = [], []                                      # paint skin, to tell a break cap seen edge-on at its seam line from a gap
    for o in bpy.data.objects:
        if o.type != 'MESH' or not o.name.startswith(('wing_', 'fus_', 'fillet_')):
            continue
        me = o.data; me.calc_loop_triangles(); M = o.matrix_world; b = len(Vs)
        Vs += [M @ v.co for v in me.vertices]
        Fs += [tuple(i + b for i in lt.vertices) for lt in me.loop_triangles if me.materials and me.materials[lt.material_index].name == 'paint']
    skin = BVHTree.FromPolygons(Vs, Fs)
    br0 = S.span_built(S.WING_BREAKS[0])

    def solid(p):
        """inside the fuselage body (5 mm margin) or inside the wing (between the skins, 5 mm margin)."""
        ax = abs(p.x)
        zt, zb, hw, zw, nt, nb = AP.body_params(p.y)
        if zb + 0.005 < p.z < zt - 0.005 and ax < AP.body_ring_x(p.y, p.z) - 0.005 and -2.6 < p.y < 1.2:
            return True
        st = AP.wing_station(min(ax, 6.0), 1)
        s = (st.le.y - p.y) / st.chord
        if 0.003 < s < 0.97 and ax > 0.3:                  # r8c: the LE strip too (game r8b: a light crack along the LE root seam)
            return AP.lower_z(ax, p.y) + 0.004 < p.z < AP.upper_z(ax, p.y) - 0.004
        return False
    dirs = []
    for el in (-60, -30, -10, 10, 30, 60):
        for az in range(0, 360, 30):
            a, e = math.radians(az), math.radians(el)
            dirs.append(V((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e))))
    bad = []
    n = 0
    for side in (1, -1):
        y = -2.30
        while y <= 1.0:
            for ax in (0.40, 0.48, 0.56, 0.64, 0.72, 0.80):
                for z in (-0.50, -0.40, -0.30, -0.24, -0.18, -0.10, 0.0, 0.10):
                    A = V((side * ax * K, y * K, z))
                    for D in dirs:
                        if D.x * side > 0.2:          # rays coming from the far side through the whole fuselage: skip
                            continue
                        O = A - D * 6.0
                        n += 1
                        hit = None
                        for loc, nrm, ob, mat, front, dist in sc.walk(O, D, 6.0 + 0.002):
                            if front or mat in ('glass', 'sightglass'):
                                hit = (loc, ob, mat, dist)
                                break
                        if hit is not None:
                            loc, ob, mat, dist = hit
                            if mat in ('glass', 'sightglass'):
                                continue
                            if mat in ('interior', 'structure') and ob.startswith(('fus_', 'fillet_', 'wing_', 'A6M2')) and abs(loc.x) < 0.95 * K                                     and not AP.in_opening(loc):         # the root band only; the open wheel wells are not a seam
                                if ob == 'fus_center' and AP.cockpit_open(loc.x, loc.y, loc.z + 0.02):
                                    continue        # the cockpit opening (under the glass)
                                if mat == 'structure' and skin.find_nearest(loc)[3] <= 0.003:
                                    continue        # a break cap seen edge-on AT its seam line (within 3 mm of the skin): the seam itself, not a gap
                                bad.append(f'see-in {ob}/{mat} at ({loc.x:.2f},{loc.y:.2f},{loc.z:.2f}) dir {tuple(round(c, 2) for c in D)}')
                            continue
                        if solid(A) and not AP.in_opening(A):      # the open wheel wells are cavities, not solid
                            bad.append(f'see-through to ({A.x:.2f},{A.y:.2f},{A.z:.2f}) dir {tuple(round(c, 2) for c in D)}')
            y = round(y + (0.02 if 0.50 <= y <= 0.95 else 0.04), 4)       # r8c: 20 mm steps over the LE root
    R('wing-root seam (r8 review: open gap between wing and fuselage; r8c: LE strip + 20 mm steps over the LE root): ray sweep from 72 external directions at the root band, both sides: no inside face '
      'and no see-through at any angle', not bad, f'{n} rays, {len(bad)} fail' + (f'; e.g. {bad[:6]}' if bad else ''))
    return bad


def fillet_smooth(R, AP):
    """r8c (game r8b: a light triangular spike out of the fillet at the LE root, a crease): between consecutive fillet rows no point of the
    fairing moves more than 2.5x the row spacing sideways or vertically (r8b: the foot dropped 0.20 m within 37 mm at the LE, slope 5.4;
    the top edge jumped 0.12 m, slope 3.2)."""
    worst, where = 0.0, None
    nv = getattr(AP, 'FILLET_VIS', 8)
    frames = getattr(AP, 'FILLET_FRAMES', {})
    for L_, rows in AP.FILLET_ROWS.items():
        fr = frames.get(L_)
        for i, (r0, r1) in enumerate(zip(rows, rows[1:])):
            if fr:
                # r8i: rolling-ball rows lie in planes that rotate round the LE nose: the sweep direction is the mean plane normal, and
                # the slope is a point's in-plane move over its move along the sweep (= dx|dz / dy for the old y = const rows)
                t = (fr[i][1] + fr[i + 1][1]).normalized()
            else:
                t = V((0, 1, 0))
            ext = max((p - q).length for p in r0[:nv] for q in r0[:nv])
            if ext < 0.03:                                       # r8h: the fading front rows (< 30 mm across) sit in the body / wing corner, buried
                continue
            for k, (a, b) in enumerate(zip(r0[:nv], r1[:nv])):        # the visible surface: the quarter-round points + the first underside point
                d = b - a
                al = abs(d.dot(t))
                if al < 1e-6:
                    continue
                pp = d - t * d.dot(t)
                sl = (max(abs(pp.x), abs(pp.y), abs(pp.z)) if fr else max(abs(d.x), abs(d.z))) / al
                if sl > worst:
                    worst, where = sl, (L_, round(a.y, 3), k)
    R('fillet smooth (r8c, game r8b LE-root spike / crease): the visible fairing surface (quarter round + foot) moves <= 2.5 x the row spacing between consecutive rows', worst <= 2.5, f'worst slope {worst:.2f} at {where}')


BREAK0 = 0.553 * 1.0057   # wing_C / wing_inner break (a6m2_spec WING_BREAKS[0] built)
SHALLOW_DEG = 8.0     # r8d: two part skins crossing at under 8 deg (or coplanar) z-fight / break up into shards; steeper crossings draw a clean line


def root_junction(R, K, region=None, verbose=False):
    """r8d (r8c sheets: jagged light shards where wing, fillet and fuselage meet at the LE root). In the root region (both sides,
    |x| 0.25-0.85, y -2.4..1.1, z -0.75..0.05) on the exterior skins (paint of fus_* / wing_* / fillet_*):
      a) VISIBLE SHALLOW CROSSINGS: two triangles of DIFFERENT parts that intersect (BVHTree.overlap) at a dihedral angle under SHALLOW_DEG (8 deg)
         (or coplanar opposite); neighbours sharing an edge across a part break are a seam, not an overlap;
         c) PARALLEL LAYERS: a visible paint triangle with another paint face within 2.2 mm along its normal at < 8 deg (z-fight) - such pairs render as jagged shards / z-fight - and whose crossing is visible from outside
         (a ray from 24 directions reaches one of the two triangles' centroids first);
      b) FLIPPED NORMALS: a paint triangle whose own normal ray (from 1 mm off its face, outward) first hits a BACK face OF ITS OWN PART, i.e. goes into
         the body it belongs to, and that is visible from outside (reached by an outside ray from at least one direction).
    Returns the failing items."""
    import mathutils
    import a6m2_parts as AP
    rg = region or dict(x0=0.25, x1=0.85, y0=-2.4 * K, y1=1.1 * K, z0=-0.75, z1=0.05)
    sc = Scene(skip=('ckcanopy_', 'pilot', 'store_'))          # the cockpit tub stays: rays through the open cockpit must not see the body's inside
    objs = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith(('fus_', 'wing_', 'fillet_'))]
    data = {}
    for o in objs:
        me = o.data; me.calc_loop_triangles(); M = o.matrix_world
        mats = [m.name if m else '' for m in me.materials]
        Vw = [M @ v.co for v in me.vertices]
        tris, cents, nrms, srcs = [], [], [], []
        srcA = me.attributes.get('src')
        for lt in me.loop_triangles:
            if mats[lt.material_index] != 'paint':
                continue
            a, b, c = (Vw[i] for i in lt.vertices)
            ce = (a + b + c) / 3
            if not (rg['x0'] <= abs(ce.x) <= rg['x1'] and rg['y0'] <= ce.y <= rg['y1'] and rg['z0'] <= ce.z <= rg['z1']):
                continue
            n = (b - a).cross(c - a)
            if n.length < 2e-6:                       # r8h: < 1 mm2 (boolean needles: no pixels at any distance, normal undefined)
                continue
            tris.append((a, b, c)); cents.append(ce); nrms.append(n.normalized())
            srcs.append(srcA.data[lt.polygon_index].value if srcA is not None else -1)
        if tris:
            vv, ff = [], []
            for t in tris:
                k = len(vv); vv += list(t); ff.append((k, k + 1, k + 2))
            data[o.name] = (BVHTree.FromPolygons(vv, ff, epsilon=0.0), cents, nrms, tris, srcs)
    dirs = []
    for el in (-60, -20, 20, 60):
        for az in range(0, 360, 60):
            a, e = math.radians(az + (30 if el in (-20, 60) else 0)), math.radians(el)
            dirs.append(V((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e))))

    def visible(p, n, obj):
        for D in dirs:
            if D.dot(n) >= -0.05:                      # only rays arriving onto the face's front side
                continue
            O = p - D * 4.0
            for loc, nr, ob, mat, front, dist in sc.walk(O, D, 4.2):
                if mat in ('glass', 'sightglass'):
                    continue
                if (loc - p).length < 0.0015 and ob == obj:
                    if verbose:
                        print('VIS', obj, tuple(round(c, 3) for c in p), 'n', tuple(round(c, 2) for c in n), 'dir', tuple(round(c, 2) for c in D))
                    return True
                break
        return False
    bad_x, bad_f = [], []
    names = sorted(data)

    def near_well(p):                                  # the wheel-well rims (a 50 mm band 1.5 mm under the lower skin over the stepped cut, by design) are excluded
        if abs(abs(p.x) - 0.0) > 0.3 and abs(p.z - (AP.lower_z(abs(p.x), p.y) - 0.0015)) < 0.0008:
            return True                                # a rim face (built at lower_z - 1.5 mm)
        return any(AP.in_opening(p + V((math.cos(a) * 0.15, math.sin(a) * 0.15, 0.0))) for a in [k * math.pi / 4 for k in range(8)]) or AP.in_opening(p)
    for i, a_ in enumerate(names):
        for b_ in names[i + 1:]:
            ta, ca, na, ra, _sa = data[a_]; tb, cb, nb, rb, _sb = data[b_]
            for ia, ib in ta.overlap(tb):
                shared = sum(1 for p in ra[ia] if any((p - q).length < 0.0005 for q in rb[ib]))
                if shared >= 1:
                    continue                                   # neighbours across a part break (shared vertex / edge): touching at the seam, no overlap
                if a_.startswith('wing_') and b_.startswith('wing_') and all(abs(abs(p.x) - BREAK0) < 0.012 for p in list(ra[ia]) + list(rb[ib])):
                    continue                                   # wing_C / wing_inner meeting ON the break plane (touching along it, no area overlap)
                d = abs(na[ia].dot(nb[ib]))
                if d < math.cos(math.radians(SHALLOW_DEG)):
                    continue
                if near_well(ca[ia]) or near_well(cb[ib]):
                    continue
                for c_, n_, o_ in ((ca[ia], na[ia], a_), (cb[ib], nb[ib], b_)):
                    if visible(c_, n_, o_):
                        bad_x.append(f'{a_}/{b_} at ({c_.x:.2f},{c_.y:.2f},{c_.z:.2f}) {math.degrees(math.acos(min(d, 1.0))):.0f} deg')
                        break
    import a6m2_parts as AP
    for nm in names:
        t, cs, ns, _, sr = data[nm]
        for c_, n_, sv in zip(cs, ns, sr):
            on_wing = False
            if nm == 'fus_center' and sv == 1:                     # r8e: the unified root carries the wing centre section: its wing skin faces take the wing rule
                ax_ = abs(c_.x)
                st_ = AP.wing_station(min(ax_, 6.0), 1)
                s2 = (st_.le.y - c_.y) / st_.chord
                on_wing = 0.02 < s2 < 0.98 and min(abs(c_.z - AP.upper_z(ax_, c_.y)), abs(c_.z - AP.lower_z(ax_, c_.y))) < 0.004
            if nm.startswith('wing_') or on_wing:      # wings: the normal must point away from the section's mid surface (ray tests at the
                ax = abs(c_.x)                         # LE root ran into the cowl and the body)
                st = AP.wing_station(min(ax, 6.0), 1)
                s_ = (st.le.y - c_.y) / st.chord
                if not (0.02 < s_ < 0.98):
                    continue
                mid = 0.5 * (AP.upper_z(ax, c_.y) + AP.lower_z(ax, c_.y))
                flip = n_.z * (c_.z - mid) < 0 and abs(n_.z) > 0.5
            else:
                hit = next(sc.walk(c_ + n_ * 0.001, n_, 3.0), None)
                flip = hit is not None and not hit[4] and hit[2] == nm and hit[3] not in ('glass', 'sightglass') and (hit[0] - c_).length > 0.003
                if flip:                               # and its other side really is outside (the cowl's two-sided skin / exhaust pipes are not flips)
                    back = next(sc.walk(c_ - n_ * 0.001, -n_, 3.0), None)
                    flip = back is None or back[4] or back[2] != nm
            if flip and visible(c_, n_, nm):
                bad_f.append(f'{nm} at ({c_.x:.2f},{c_.y:.2f},{c_.z:.2f})')
    bad_c = []
    for nm in names:
        t, cs, ns, _, _s = data[nm]
        for c_, n_ in zip(cs, ns):
            for sgn in (1, -1):
                h = sc.tree.ray_cast(c_ + n_ * (sgn * 0.0002), n_ * sgn, 0.0022)
                if h[0] is None:
                    continue
                ob2, mat2 = sc.meta[h[2]]
                if mat2 == 'paint' and abs(h[1].dot(n_)) > math.cos(math.radians(SHALLOW_DEG)) and h[3] > 0.0003 and not near_well(c_) and not near_well(h[0]) and visible(c_, n_, nm):
                    bad_c.append(f'{nm}/{ob2} layer {h[3] * 1000:.1f} mm at ({c_.x:.2f},{c_.y:.2f},{c_.z:.2f})')
                    break
    bad_x += bad_c
    R('root junction (r8d, r8c sheets: shards at the wing / fillet / fuselage junction): no VISIBLE intersecting triangles of two parts at a near-coplanar '
      '(< 8 deg) angle, and no visible flipped paint normal, both sides, |x| 0.25-0.85, y -2.4..1.1',
      not bad_x and not bad_f, f'{len(bad_x)} shallow crossings, {len(bad_f)} flipped' + (f'; e.g. {(bad_x[:5] + bad_f[:5])}' if bad_x or bad_f else ''))
    return bad_x, bad_f


def root_unified(R, K):
    """r8e (coordinator: build the wing-fuselage junction as ONE mesh). Within 0.4 m of the wing / fuselage intersection (|x| <= 0.90,
    y -2.65..0.86, z -0.75..0.10, both sides; ahead of y 0.86 the cowl / chin belong to fus_engine):
      a) every VISIBLE skin face belongs to the one root mesh fus_center (gear legs / doors, flaps, guns and stores excepted);
      b) no visible fus_center face has another part's skin within 5 mm along its normal (no layered sheets);
      c) the root mesh's VISIBLE skin is manifold there: no edge of a face seen from outside has more than two faces, and open edges only
         on the designed openings (joint rings to fus_engine / fus_rear, the cockpit opening above z 0.55); buried boolean fragments are counted."""
    import bmesh
    sc = Scene(skip=('ckcanopy_', 'pilot', 'store_'))
    fc = bpy.data.objects['fus_center']
    me = fc.data; me.calc_loop_triangles(); M = fc.matrix_world
    mats = [m.name if m else '' for m in me.materials]
    other_ok = ('gear_', 'flap_', 'cannon', 'pitot', 'aerial', 'rack_', 'tailhook', 'exhaust', 'cockpit_', 'gauge_', 'canopy_', 'prop')
    # the chin oil-cooler scoop under the belly (|x| < 0.2, ahead of y 0.45) is part of the ENGINE (fus_engine detaches with it): a separate
    # component standing 3-4 mm off the belly by design, not part of the wing-fuselage junction
    chin = lambda p: abs(p.x) < 0.20 and p.y > 0.45

    def in_rg(p):
        return abs(p.x) <= 0.90 and -2.65 <= p.y <= 0.86 and -0.75 <= p.z <= 0.10
    dirs = []
    for el in (-70, -35, 0, 35, 70):
        for az in range(0, 360, 45):
            a, e = math.radians(az + (22.5 if el in (-35, 35) else 0)), math.radians(el)
            dirs.append(V((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e))))
    # a) sample visible surface points in the region: rays from outside toward a grid of target points; the FIRST skin hit decides
    foreign = {}
    n = 0
    for side in (1, -1):
        y = -2.6
        while y <= 0.84:
            for ax in (0.30, 0.42, 0.54, 0.66, 0.78, 0.88):
                for z in (-0.60, -0.45, -0.35, -0.25, -0.15, -0.05):
                    tgt = V((side * ax, y, z))
                    for D in dirs:
                        if D.x * side > 0.3:
                            continue
                        O = tgt - D * 5.0
                        for loc, nr, ob, mat, front, dist in sc.walk(O, D, 6.0):
                            if mat in ('glass', 'sightglass'):
                                continue
                            if not in_rg(loc):
                                break
                            n += 1
                            if ob != 'fus_center' and not ob.startswith(other_ok) and mat == 'paint' and not (ob == 'fus_engine' and chin(loc)):
                                foreign[ob] = foreign.get(ob, 0) + 1
                            break
            y = round(y + 0.10, 4)
    # b) layered sheets: from visible fus_center paint faces in the region, 5 mm along +-n
    layered = []
    for lt in me.loop_triangles:
        if mats[lt.material_index] != 'paint':
            continue
        c = M @ lt.center
        if not in_rg(c):
            continue
        nn = (M.to_3x3() @ lt.normal).normalized()
        for sgn in (1, -1):
            h = sc.tree.ray_cast(c + nn * (sgn * 0.0003), nn * sgn, 0.005)
            if h[0] is None:
                continue
            ob2, mat2 = sc.meta[h[2]]
            if ob2 != 'fus_center' and mat2 == 'paint' and not ob2.startswith(other_ok) and not (ob2 == 'fus_engine' and chin(c)):
                layered.append(f'{ob2} {h[3] * 1000:.1f} mm at ({c.x:.2f},{c.y:.2f},{c.z:.2f})')
                break
    # c) manifold in the region
    bm = bmesh.new(); bm.from_mesh(me); bm.transform(M)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    ymin = min(v.co.y for v in bm.verts); ymax = max(v.co.y for v in bm.verts)
    nm3, opn = [], []
    hidden_e = 0
    from mathutils.bvhtree import BVHTree as _BVH
    jtrees = []                                        # the designed joint rings: open skin edges ON the cowl / rear-fuselage
    for jn in ('fus_engine', 'fus_rear'):              # surface (within 4 mm) are the part joints, not holes
        jo = bpy.data.objects.get(jn)
        if jo is not None:
            jb = bmesh.new(); jb.from_mesh(jo.data); jb.transform(jo.matrix_world)
            jtrees.append(_BVH.FromBMesh(jb)); jb.free()
    joint_e = 0
    for e in bm.edges:
        c = (e.verts[0].co + e.verts[1].co) / 2
        if not in_rg(c):
            continue
        import a6m2_parts as AP
        zt_, zb_ = AP.body_params(c.y)[0], AP.body_params(c.y)[1]
        if zb_ + 0.004 < c.z < zt_ - 0.004 and abs(c.x) < AP.body_ring_x(c.y, c.z) - 0.004:
            continue                                   # inside the fuselage hull: hidden (boolean leftovers removed there)
        stw = AP.wing_station(min(abs(c.x), 6.0), 1); sw = (stw.le.y - c.y) / stw.chord
        if 0.01 < sw < 0.99 and AP.lower_z(abs(c.x), c.y) + 0.003 < c.z < AP.upper_z(abs(c.x), c.y) - 0.003:
            continue                                   # inside the wing solid: hidden
        lf = [f for f in e.link_faces if mats[f.material_index] in ('paint', 'well')]     # the skin (+ well walls): tub / internals are open sheets
        if not lf:
            continue
        if len(lf) == 1 and len(e.link_faces) == 2:   # skin closed by an interior face (the firewall cap at the cowl ring)
            continue
        bad_e = len(lf) > 2 or (len(lf) < 2 and not (c.y > ymax - 0.02 or c.y < ymin + 0.02 or c.z > 0.55))
        if not bad_e:
            continue
        seen_ = False                                  # only edges of VISIBLE skin count; buried boolean fragments (inside the
        for f in lf:                                   # fuselage, the wing or the fairing solid) are hidden
            fc_ = f.calc_center_median(); fn_ = f.normal
            for D in dirs:
                for sg in (1, -1):
                    if (D * sg).dot(fn_) >= -0.05:
                        continue
                    h = sc.tree.ray_cast(fc_ - D * sg * 4.0, D * sg, 4.2)
                    if h[0] is not None and (h[0] - fc_).length < 0.002:
                        seen_ = True; break
                if seen_:
                    break
            if seen_:
                break
        if not seen_:
            hidden_e += 1
            continue
        if len(lf) < 2 and any(t.find_nearest(c, 0.004)[0] is not None for t in jtrees):
            joint_e += 1
            continue
        if len(lf) > 2:
            nm3.append(tuple(round(v, 2) for v in c))
        else:
            opn.append(tuple(round(v, 2) for v in c))
    bm.free()
    # d) r8g (game r8f: a light flat wedge at the LE root - fairing loops with sideways normals): the SHADING normals of the root mesh's
    #    paint faces in the region: no loop normal more than 60 deg off its own face, and no shading seam on smooth surface (two faces
    #    meeting at < 20 deg whose loop normals at a shared vertex differ by > 20 deg)
    R3_ = M.to_3x3(); cn_ = me.corner_normals
    pi_ = mats.index('paint')
    offf, seams = [], []
    lo_ = {}; em_ = {}
    for p_ in me.polygons:
        if p_.material_index != pi_:
            continue
        c_ = M @ p_.center
        fn_ = (R3_ @ p_.normal).normalized()
        if in_rg(c_) and any((R3_ @ cn_[li].vector).normalized().dot(fn_) < 0.5 for li in p_.loop_indices):
            offf.append(tuple(round(v, 2) for v in c_))
        for li in p_.loop_indices:
            lo_[(p_.index, me.loops[li].vertex_index)] = li
        for ek in p_.edge_keys:
            em_.setdefault(ek, []).append(p_.index)
    c20 = math.cos(math.radians(20.0))
    for ek, fl in em_.items():
        if len(fl) != 2:
            continue
        pa, pb = me.polygons[fl[0]], me.polygons[fl[1]]
        c_ = M @ ((me.vertices[ek[0]].co + me.vertices[ek[1]].co) / 2)
        if not in_rg(c_) or (R3_ @ pa.normal).normalized().dot((R3_ @ pb.normal).normalized()) < c20:
            continue
        for v in ek:
            if (R3_ @ cn_[lo_[(pa.index, v)]].vector).normalized().dot((R3_ @ cn_[lo_[(pb.index, v)]].vector).normalized()) < c20:
                seams.append(tuple(round(x_, 2) for x_ in c_)); break
    ok = not foreign and not layered and not nm3 and not opn and not offf and not seams
    R('root unified (r8e: ONE mesh at the wing-fuselage junction): within 0.4 m of the root every visible skin hit is fus_center, no other '
      'skin within 5 mm of it, manifold (no edge with > 2 faces, no open edge off the designed openings); r8g: no shading normal > 60 deg off '
      'its face and no shading seam > 20 deg on smooth (< 20 deg) surface', ok,
      f'{n} visible hits, foreign {foreign}, layered {len(layered)} {layered[:3]}, visible >2-face edges {len(nm3)} {nm3[:3]}, visible open edges {len(opn)} {opn[:4]}; buried fragment edges (not seen from outside) {hidden_e}, open edges on the cowl / rear joint rings {joint_e}; '
      f'off-face shading normals {len(offf)} {offf[:4]}, shading seams {len(seams)} {seams[:4]}')
    return foreign, layered, nm3, opn


def cockpit_contained(R, AP, K):
    """r8: no cockpit part pokes out through the fuselage side (r7: the right console box and the floor edges stood 10-60 mm outside the
    skin - green slots on the fuselage side above the wing root). Every vertex of cockpit_* / gauge_* meshes that lies in the cockpit bay
    (y -0.2..-1.5) and under the canopy base must be inside the outer skin ring (|x| <= ring x at its height + 1 mm)."""
    bad = []
    n = 0
    for o in bpy.data.objects:
        if o.type != 'MESH' or not o.name.startswith(('cockpit_', 'gauge_')):
            continue
        M = o.matrix_world
        for v in o.data.vertices:
            p = M @ v.co
            if not (-1.5 * K < p.y < -0.2 * K):
                continue
            xs = S_canopy_base(AP, p.y)
            if p.z > xs[1] - 0.005:
                continue
            n += 1
            lim = AP.body_ring_x(p.y, p.z)
            if abs(p.x) > lim + 0.001:
                bad.append(f'{o.name} ({p.x:.3f},{p.y:.3f},{p.z:.3f}) {1000 * (abs(p.x) - lim):.0f} mm out')
    R('cockpit parts inside the fuselage skin (r8: r7 console box and floor edges poked through the side)', not bad,
      f'{n} vertices, {len(bad)} outside' + (f'; {bad[:6]}' if bad else ''))


def S_canopy_base(AP, yb):
    import a6m2_spec as S
    xs = S.lin(S.CANOPY, yb / S.K, 1) * S.K
    return xs, AP.body_z_at(xs, yb)


def livery_uv_sane(R, res=2048):
    """r8h (r8h liveries: a bite out of the IJN fuselage hinomaru): boolean-sealed slits had loops with UVs from different atlas islands,
    and those faces spanned the atlas, so the livery bake painted them over other islands. Every paint face's livery texel density must be
    under 3x the model's median (no face spans the atlas)."""
    import math
    dens, bad = [], []
    for o in bpy.data.objects:
        if o.type != 'MESH' or 'livery' not in o.data.uv_layers:
            continue
        me = o.data; uv = me.uv_layers['livery']; mats = [m.name if m else '' for m in me.materials]
        for p in me.polygons:
            if mats[p.material_index] != 'paint' or p.area < 1e-6:
                continue
            pts = [uv.data[l].uv for l in p.loop_indices]; ua = 0.0
            for i in range(1, len(pts) - 1):
                ua += abs((pts[i].x - pts[0].x) * (pts[i + 1].y - pts[0].y) - (pts[i + 1].x - pts[0].x) * (pts[i].y - pts[0].y)) / 2
            d = math.sqrt(ua / p.area) * res
            dens.append(d)
            if d > 0:
                bad.append((d, o.name, tuple(round(v, 2) for v in (o.matrix_world @ p.center))))
    med = sorted(dens)[len(dens) // 2] if dens else 0
    off = [b for b in bad if b[0] > 10 * med]           # (tip caps / small planar islands reach ~7x; atlas-spanning faces are 100x+)
    R('livery UV sanity (r8h: sealed slits spanned the atlas and painted over other islands): no paint face above 10x the median texel density',
      not off, f'median {med:.0f} texels/m, {len(dens)} faces, over 10x: {len(off)} {[(round(b[0]), b[1], b[2]) for b in sorted(off, reverse=True)[:4]]}')



def _pose_gear_up():
    """r8j/r8k: flight pose for the ray checks - main legs stowed about the contract axis, inner well doors closed; returns the saved
    matrices for _restore."""
    import json
    from mathutils import Quaternion, Matrix
    saved = {}

    def _rot(piv, axis, deg):
        return Matrix.Translation(piv) @ Quaternion(V(axis), math.radians(deg)).to_matrix().to_4x4() @ Matrix.Translation(-piv)
    for L in 'LR':
        s = bpy.data.objects.get(f'gear_main_{L}_strut')
        if s is None or 'b25_info' not in s:
            continue
        inf = json.loads(s['b25_info']); saved[s.name] = s.matrix_world.copy()
        s.matrix_world = _rot(V(inf['pivot']), inf['retract_axis_world'], inf['retract_deg']) @ s.matrix_world
    bpy.context.view_layer.update()
    for L in 'LR':
        d = bpy.data.objects.get(f'gear_door_{L}')
        if d is None or 'b25_info' not in d:
            continue
        inf = json.loads(d['b25_info']); saved[d.name] = d.matrix_world.copy()
        piv = d.matrix_world.translation.copy(); best = None
        for sg in (inf['open_deg'], -inf['open_deg']):           # closed = the sense that lays the door flat (smallest z spread)
            m = _rot(piv, inf['hinge_axis'], sg) @ d.matrix_world
            zs = [(m @ v.co).z for v in d.data.vertices]
            if best is None or max(zs) - min(zs) < best[0]:
                best = (max(zs) - min(zs), m)
        d.matrix_world = best[1]
    bpy.context.view_layer.update()
    return saved


def _restore(saved):
    for nm, m in saved.items():
        bpy.data.objects[nm].matrix_world = m
    bpy.context.view_layer.update()

def le_root_sweep(R, step_v=0.003, step_s=0.004, cam_res=(320, 200)):
    """r8j (in game r8i: a teal sliver and a dark notch under the LE root, read as an open gap). Flight pose: main legs stowed about the
    contract axis, inner well doors closed. Ray sweeps into the nose / LE-root box (|x| < 0.75, y 0.25-1.30, z -0.80..-0.10):
      * vertical (from below and from above, step_v grid): no first hit on a BACK face (looking into the skin through a hole);
      * lateral (from -x and +x at x 1.6, step_s grid, y 0.70-1.30): no miss enclosed by the airframe (a see-through slot)
        and no BACK first hit;
      * six cameras (below-front, front-low, side-front, both sides): no BACK first hit, no enclosed miss, and no aotake ('well') face of
        a moving part (leg cover, wheel, door) seen from outside with the gear up.
    The r8i model fails it three ways: the leg cover's aotake edge band (the teal sliver), a slot between the chin and the raised belly
    ahead of the centre LE (seen through from the side), and the right inner skin poking 3 mm out under the LE root."""
    saved = _pose_gear_up()
    try:
        SKIP = ('gear_tail', 'store_', 'prop', 'pitot', 'cockpit', 'gauge', 'ck', 'canopy', 'aerial', 'hp_')
        verts, tris, info = [], [], []
        for o in bpy.data.objects:
            if o.type != 'MESH' or o.name.startswith(SKIP) or o.hide_render:
                continue
            me = o.data; me.calc_loop_triangles(); mw = o.matrix_world; b = len(verts)
            mats = [m.name if m else '' for m in me.materials]
            verts += [mw @ v.co for v in me.vertices]
            moving = o.name.startswith(('gear_main', 'gear_door'))
            for t in me.loop_triangles:
                tris.append(tuple(b + i for i in t.vertices)); info.append((o.name, mats[me.polygons[t.polygon_index].material_index], moving))
        bvh = BVHTree.FromPolygons(verts, tris, all_triangles=True)
        back_v, back_pts = 0, []
        nx, ny = int(1.5 / step_v), int(1.05 / step_v)
        for i in range(nx):
            x = -0.75 + (i + 0.5) * step_v
            for j in range(ny):
                y = 0.25 + (j + 0.5) * step_v
                for dz in (1.0, -1.0):
                    loc, n, idx, _ = bvh.ray_cast(V((x, y, -2.0 * dz)), V((0, 0, dz)), 4.0)
                    if loc is not None and n.z * dz > 0:
                        back_v += 1; back_pts.append((round(x, 3), round(y, 3), round(loc.z, 3), info[idx][0], info[idx][1]))

        def enclosed(miss):            # miss cells not 4-connected to the grid border
            H_, W_ = len(miss), len(miss[0]); seen = [[False] * W_ for _ in range(H_)]; st = []
            for j in range(H_):
                for i in (0, W_ - 1):
                    if miss[j][i]:
                        st.append((j, i))
            for i in range(W_):
                for j in (0, H_ - 1):
                    if miss[j][i]:
                        st.append((j, i))
            while st:
                j, i = st.pop()
                if not (0 <= j < H_ and 0 <= i < W_) or seen[j][i] or not miss[j][i]:
                    continue
                seen[j][i] = True
                st += [(j + 1, i), (j - 1, i), (j, i + 1), (j, i - 1)]
            return [(j, i) for j in range(H_) for i in range(W_) if miss[j][i] and not seen[j][i]]
        lat_enc, lat_back, lat_pts = 0, 0, []
        ys = [1.30 - (k + 0.5) * step_s for k in range(int(0.60 / step_s))]     # y 0.70-1.30: ahead of the wing at x 1.6 (rays start outside it)
        zs = [-0.10 - (k + 0.5) * step_s for k in range(int(0.70 / step_s))]
        for sx in (1.0, -1.0):
            miss = []
            for z in zs:
                row = []
                for y in ys:
                    loc, n, idx, _ = bvh.ray_cast(V((-1.6 * sx, y, z)), V((sx, 0, 0)), 3.2)
                    row.append(loc is None)
                    if loc is not None and n.x * sx > 0:
                        lat_back += 1
                miss.append(row)
            e = enclosed(miss)
            lat_enc += len(e)
            lat_pts += [(round(ys[i], 3), round(zs[j], 3)) for j, i in e[:: max(1, len(e) // 4)]][:4]
        cams = {'below_front': ((-1.5, 1.9, -1.0), (-0.62, 0.70, -0.42)), 'front_low': ((-1.9, 2.1, -0.15), (-0.65, 0.68, -0.45)),
                'side_front': ((-2.2, 1.2, -0.35), (-0.62, 0.68, -0.42))}
        cams.update({k + '_R': ((-c[0], c[1], c[2]), (-t[0], t[1], t[2])) for k, (c, t) in list(cams.items())})
        W_, H_ = cam_res
        th = math.tan(math.radians(30.0) / 2)
        cam_out = {}
        for cn, (cp, tp) in cams.items():
            C = V(cp); T = V(tp); f = (T - C).normalized(); r = f.cross(V((0, 0, 1))).normalized(); u = r.cross(f)
            miss = []; nb = nw = 0; wpts = []
            for j in range(H_):
                row = []
                for i in range(W_):
                    d = (f + r * ((2 * (i + .5) / W_ - 1) * th) + u * ((1 - 2 * (j + .5) / H_) * th * H_ / W_)).normalized()
                    loc, n, idx, _ = bvh.ray_cast(C, d, 30.0)
                    row.append(loc is None)
                    if loc is None:
                        continue
                    if n.dot(d) > 0:
                        nb += 1
                    elif info[idx][2] and info[idx][1] == 'well':
                        nw += 1; wpts.append(tuple(round(c, 3) for c in loc))
                miss.append(row)
            cam_out[cn] = (nb, len(enclosed(miss)), nw, wpts[:: max(1, len(wpts) // 3)][:3])
        cam_bad = {k: v for k, v in cam_out.items() if v[0] or v[1] or v[2]}
        ok = back_v == 0 and lat_enc == 0 and lat_back == 0 and not cam_bad
        R('LE-root ray sweep, gear up (r8j: in game r8i a teal sliver + dark notch under the LE root): vertical sweeps hit no back face, '
          'lateral sweeps find no see-through slot or back face, 6 cameras see no back face, no enclosed sky and no aotake on a gear cover / door',
          ok, f'vertical {nx}x{ny}x2 rays: back {back_v} {back_pts[:3]}; lateral: enclosed miss {lat_enc} {lat_pts}, back {lat_back}; '
              f'cameras (back, enclosed, cover aotake px): {dict((k, v[:3]) for k, v in cam_out.items())} {dict((k, v[3]) for k, v in cam_bad.items())}')
    finally:
        _restore(saved)


def gear_bay_sweep(R, step=0.002, tilt_deg=30.0, max_band=0.012):
    """r8k (in game r8j, gear up: a light-blue crescent and a dark sliver at the inboard edge of each closed main well - the round
    opening ran 27 mm inboard of the inner door's hinge edge). Flight pose (_pose_gear_up). Over each well (|x| 0-0.85, y -0.05..0.80),
    parallel ray grids (step) from below - straight up and tilted tilt_deg inboard / outboard / forward / aft - must not see the well
    (aotake 'well' faces) or sky past the closed covers in a band wider than max_band (the cover edge gap is 4 mm; the r8j crescent ~25 mm),
    and no ray may get through to the sky inside the airframe outline."""
    import numpy as np
    saved = _pose_gear_up()
    try:
        SKIP = ('gear_tail', 'store_', 'prop', 'pitot', 'cockpit', 'gauge', 'ck', 'canopy', 'aerial', 'hp_')
        verts, tris, mt = [], [], []
        for o in bpy.data.objects:
            if o.type != 'MESH' or o.name.startswith(SKIP) or o.hide_render:
                continue
            me = o.data; me.calc_loop_triangles(); mw = o.matrix_world; b = len(verts)
            mats = [m.name if m else '' for m in me.materials]
            verts += [mw @ v.co for v in me.vertices]
            for t in me.loop_triangles:
                tris.append(tuple(b + i for i in t.vertices)); mt.append(mats[me.polygons[t.polygon_index].material_index])
        bvh = BVHTree.FromPolygons(verts, tris, all_triangles=True)
        ta = math.radians(tilt_deg)
        out, worst, ok = {}, 0.0, True
        nx, ny = int(0.85 / step), int(0.85 / step)
        for side in (1, -1):
            dirs = {'up': V((0, 0, 1)), 'in': V((-side * math.sin(ta), 0, math.cos(ta))), 'out': V((side * math.sin(ta), 0, math.cos(ta))),
                    'fwd': V((0, math.sin(ta), math.cos(ta))), 'aft': V((0, -math.sin(ta), math.cos(ta)))}
            for dn, d in dirs.items():
                well = np.zeros((ny, nx), bool); hit = np.zeros((ny, nx), bool)
                for j in range(ny):
                    y = -0.05 + (j + 0.5) * step
                    for i in range(nx):
                        x = side * (i + 0.5) * step
                        o_ = V((x, y, -0.55)) - d * 1.5
                        loc, n, idx, _ = bvh.ray_cast(o_, d, 3.0)
                        if loc is None:
                            continue
                        hit[j, i] = True
                        if mt[idx] in ('well', 'well_dark'):
                            well[j, i] = True
                # sky enclosed by the airframe = a miss whose row has hits on both sides and whose column has hits on both sides
                enc = 0
                for j in range(ny):
                    r_ = np.where(hit[j])[0]
                    if len(r_) > 1:
                        seg = ~hit[j, r_.min():r_.max()]
                        for i in np.where(seg)[0] + r_.min():
                            c_ = np.where(hit[:, i])[0]
                            if len(c_) > 1 and c_.min() < j < c_.max():
                                enc += 1
                # band width of the exposed well: erode until nothing is left (4-neighbourhood); width ~ 2 x erosions x step
                m = well.copy(); k = 0
                while m.any() and k < 60:
                    m = m & np.roll(m, 1, 0) & np.roll(m, -1, 0) & np.roll(m, 1, 1) & np.roll(m, -1, 1)
                    k += 1
                band = 2 * k * step
                worst = max(worst, band)
                out[f"{'R' if side > 0 else 'L'}_{dn}"] = (int(well.sum()), round(band * 1000), enc)
                if band > max_band or enc:
                    ok = False
        R('gear bay sweep, gear up (r8k: in game r8j a light-blue crescent at the inboard edge of each closed well): parallel rays from below '
          f'(up, +-{tilt_deg:.0f} deg in / out / fwd / aft) see no well band wider than {max_band * 1000:.0f} mm past the closed covers and no sky',
          ok, f'per grid (well cells, widest band mm, enclosed sky): {out}; widest {worst * 1000:.0f} mm')
    finally:
        _restore(saved)


def well_detail_clear(R, min_bars=200):
    """r8l: the well ribs / rim lip (fus_center faces with src 3) exist (>= min_bars x 6 faces) and neither main leg nor wheel touches
    them at any retraction step (0..retract every 5 deg)."""
    import json
    from mathutils import Quaternion
    fc = bpy.data.objects.get('fus_center')
    me = fc.data; me.calc_loop_triangles(); mw = fc.matrix_world
    src = me.attributes.get('src')
    vs = [mw @ v.co for v in me.vertices]
    tr = [tuple(t.vertices) for t in me.loop_triangles if src is not None and src.data[t.polygon_index].value == 3]
    nfaces = sum(1 for p in me.polygons if src is not None and src.data[p.index].value == 3)
    det = BVHTree.FromPolygons(vs, tr) if tr else None
    hits = []
    for L in 'LR':
        s_ = bpy.data.objects.get(f'gear_main_{L}_strut')
        if s_ is None or det is None:
            continue
        inf = json.loads(s_['b25_info']); piv = V(inf['pivot']); ax = V(inf['retract_axis_world'])
        for o in [s_] + [c for c in s_.children_recursive if c.type == 'MESH']:
            m2 = o.data; m2.calc_loop_triangles(); w2 = o.matrix_world
            v2 = [w2 @ v.co for v in m2.vertices]; t2 = [tuple(t.vertices) for t in m2.loop_triangles]
            for dg in list(range(0, int(inf['retract_deg']) + 1, 5)) + [inf['retract_deg']]:
                q = Quaternion(ax, math.radians(dg))
                n_ = len(BVHTree.FromPolygons([piv + q @ (v - piv) for v in v2], t2).overlap(det))
                if n_:
                    hits.append((L, o.name, round(dg), n_))
    ok = det is not None and nfaces >= 6 * min_bars and not hits
    R(f'well detail (r8l: ribs + rim lip in each main well) present (>= {min_bars} bars) and clear of the main legs / wheels at every retraction step',
      ok, f'detail faces {nfaces}; contacts {hits[:6]}')


# ---------------------------------------------------------------------------------------------------- r8m (user review r8l, in game)
SEE = ('sightglass', 'reticle')
CK_SKIP = ('canopy_windscreen', 'canopy_hood', 'canopy_rear', 'pilot', 'store_', 'cockpit_eye')


def _obj_tris(o):
    me = o.data
    me.calc_loop_triangles()
    M = o.matrix_world
    vs = [M @ v.co for v in me.vertices]
    mats = [m.name if m else '' for m in me.materials]
    return vs, [(tuple(lt.vertices), mats[lt.material_index] if mats else '') for lt in me.loop_triangles]


def _islands(vs, tris, weld=0.0005, touch=0.001):
    """union-find shells of `tris` (verts welded at `weld`), then shells merged when their BVHs overlap or a vertex of one lies within
    `touch` of the other. Returns a list of vertex-index sets."""
    from mathutils.kdtree import KDTree
    used = sorted({i for t in tris for i in t})
    par = {i: i for i in used}

    def f(i):
        while par[i] != i:
            par[i] = par[par[i]]
            i = par[i]
        return i

    def u(a, b):
        a, b = f(a), f(b)
        if a != b:
            par[a] = b
    kd = KDTree(len(used))
    for j, i in enumerate(used):
        kd.insert(vs[i], j)
    kd.balance()
    for i in used:
        for _, j, _ in kd.find_range(vs[i], weld):
            u(i, used[j])
    for t in tris:
        u(t[0], t[1])
        u(t[0], t[2])
    groups = {}
    for t in tris:
        groups.setdefault(f(t[0]), []).append(t)
    isl = list(groups.values())
    trees = [BVHTree.FromPolygons(vs, g) for g in isl]
    vsets = [sorted({i for t in g for i in t}) for g in isl]
    n = len(isl)
    p2 = list(range(n))

    def f2(i):
        while p2[i] != i:
            p2[i] = p2[p2[i]]
            i = p2[i]
        return i
    for a in range(n):
        for b in range(a + 1, n):
            if f2(a) == f2(b):
                continue
            hit = bool(trees[a].overlap(trees[b]))
            if not hit:
                hit = any((trees[b].find_nearest(vs[i], touch)[0] is not None) for i in vsets[a]) or \
                    any((trees[a].find_nearest(vs[i], touch)[0] is not None) for i in vsets[b])
            if hit:
                p2[f2(a)] = f2(b)
    comp = {}
    for a in range(n):
        comp.setdefault(f2(a), set()).update(vsets[a])
    return list(comp.values())


def _first_front(sc, eye, d, maxd=3.0):
    for loc, nrm, ob, mat, front, dist in sc.walk(eye, d, maxd):
        if front:
            return (ob, mat)
    return None


def sight_mount(R, S, K):
    """r8m (user review r8l: the Type 98 glass frame floated over the sight body, seen from the seat). On cockpit_sight (world):
    1 connected - the solid (non glass / reticle) parts form ONE body (welded 0.5 mm, shells merged on overlap or <= 1 mm);
    2 glass held - every sightglass corner within 1.5 mm of the solid parts; 3 orientation - bottom edge forward, top leaning aft to the
    pilot 25..45 mm, both edges within 3 mm of WT collimator.ckpt, aft normal down; 4 clear view - 9x9 eye rays over 0.15..0.85 of the
    glass first hit the glass / reticle; 5 no floating from the eye - rays along both frame arms and a vertical fan under the glass bottom
    edge (x -0.02..0.02, 0.05 deg) all end on the sight's solid parts; 6 centred + mirror-symmetric solid parts."""
    from mathutils.kdtree import KDTree
    import a6m2_ck_layout as L
    SG = L.SIGHT
    o = bpy.data.objects.get('cockpit_sight')
    if o is None:
        R('r8m sight mount: cockpit_sight present', False, 'missing')
        return
    vs, tris = _obj_tris(o)
    SOL = [t for t, m in tris if m not in SEE]
    gl = [t for t, m in tris if m == 'sightglass']
    isl = _islands(vs, SOL)
    bbs = []
    for s_ in isl:
        lo = [min(vs[i][j] for i in s_) for j in range(3)]
        hi = [max(vs[i][j] for i in s_) for j in range(3)]
        bbs.append(tuple(round(x, 4) for x in lo + hi))
    sol_t = BVHTree.FromPolygons(vs, SOL)
    corners = []
    gxs = max((abs(vs[i].x) for t in gl for i in t), default=0.0)
    for i in sorted({i for t in gl for i in t}):
        p = vs[i]
        if abs(p.x) < 0.5 * gxs:              # prism() fans each face from its centroid: not a corner
            continue
        if all((p - q).length > 1e-5 for q in corners):
            corners.append(p.copy())
    cdist = max(sol_t.find_nearest(p)[3] for p in corners) if corners else 9.0
    cc = sum(corners, V()) / max(len(corners), 1)
    top = [p for p in corners if p.z > cc.z]
    bot = [p for p in corners if p.z <= cc.z]
    ty = sum(p.y for p in top) / max(len(top), 1)
    tz = sum(p.z for p in top) / max(len(top), 1)
    by = sum(p.y for p in bot) / max(len(bot), 1)
    bz = sum(p.z for p in bot) / max(len(bot), 1)
    lean = by - ty
    db = math.hypot(by + 0.3296 * K, bz - 0.7608 * K)
    dt = math.hypot(ty + 0.3665 * K, tz - 0.8037 * K)
    best = None                                   # aft-facing normal: the biggest glass triangle facing aft
    for t in gl:
        a, b, c = (vs[i] for i in t)
        n = (b - a).cross(c - a)
        if n.y < 0 and (best is None or n.length > best.length):
            best = n
    gn = best.normalized() if best is not None else V((0, -1, 0))
    orient_ok = len(corners) == 8 and 0.025 <= lean <= 0.045 and db <= 0.003 and dt <= 0.003 and gn.z < 0
    eo = bpy.data.objects.get('cockpit_eye')
    eye = eo.matrix_world.translation.copy() if eo is not None else V(S.pre(S.EYE, plug=False))
    sc = Scene(skip=CK_SKIP)
    es = [p for p in corners if (p - cc).dot(gn) > 0]         # eye-side face corners
    es_b = sorted([p for p in es if p.z < cc.z], key=lambda p: p.x)
    es_t = sorted([p for p in es if p.z >= cc.z], key=lambda p: p.x)
    clear, nclear, bad4 = 0, 0, []
    if len(es_b) == 2 and len(es_t) == 2:
        for iu in range(9):
            for iv in range(9):
                uu, vv = 0.15 + 0.7 * iu / 8, 0.15 + 0.7 * iv / 8
                P = es_b[0].lerp(es_b[1], uu).lerp(es_t[0].lerp(es_t[1], uu), vv)
                nclear += 1
                first = _first_front(sc, eye, (P - eye).normalized())
                if first is not None and first[0] == 'cockpit_sight' and first[1] in SEE:
                    clear += 1
                else:
                    bad4.append((round(uu, 2), round(vv, 2), first))
    gaps, nray = [], 0
    gh = max(abs(p.x) for p in corners) if corners else 0.026
    hy = SG.get('hinge_y', -0.330) * K
    hz = SG.get('head_z', 0.743) * K + 0.001
    for s_ in (-1, 1):                            # 5a rays along both arms: head plate top -> glass top corner (+2 mm out)
        tcs = [p for p in corners if p.z > cc.z and s_ * p.x > 0]
        tc = max(tcs, key=lambda p: p.z) if tcs else V()
        a_ = V((s_ * (gh + 0.002), hy, hz))
        b_ = tc + V((s_ * 0.002, 0, 0))
        for k in range(51):
            P = a_.lerp(b_, k / 50)
            nray += 1
            first = _first_front(sc, eye, (P - eye).normalized())
            if not (first is not None and first[0] == 'cockpit_sight' and first[1] not in SEE):
                gaps.append(('arm', s_, k, first))
    yb_ = sum(p.y for p in es_b) / 2 if len(es_b) == 2 else by     # 5b vertical fan: glass bottom edge -> head plate top aft edge
    zb_ = sum(p.z for p in es_b) / 2 if len(es_b) == 2 else bz
    yp_ = -0.379 * K
    zp_ = SG.get('head_z', 0.743) * K
    e_top = math.degrees(math.atan2(zb_ - eye.z, yb_ - eye.y))
    e_bot = math.degrees(math.atan2(zp_ - eye.z, yp_ - eye.y))
    nfan = 0
    for ix in range(9):
        x = -0.02 + 0.005 * ix
        e = e_top - 0.05
        while e > e_bot + 0.05:
            T = V((x, yb_, eye.z + math.tan(math.radians(e)) * (yb_ - eye.y)))
            nfan += 1
            first = _first_front(sc, eye, (T - eye).normalized())
            if not (first is not None and first[0] == 'cockpit_sight' and first[1] not in SEE):
                gaps.append(('fan', round(x, 3), round(e, 2), first))
            e -= 0.05
    sv = sorted({i for t in SOL for i in t})
    allv = sorted({i for t, m in tris for i in t})
    cx = (min(vs[i].x for i in allv) + max(vs[i].x for i in allv)) / 2
    kd = KDTree(len(sv))
    for j, i in enumerate(sv):
        kd.insert(vs[i], j)
    kd.balance()
    worst_m = max(kd.find(V((-vs[i].x, vs[i].y, vs[i].z)))[2] for i in sv)
    sym_ok = abs(cx) <= 0.001 and worst_m <= 0.0005
    R('r8m sight mount (user review r8l: frame floated over the sight): 1 connected (one solid body), 2 glass corners held (<= 1.5 mm), 3 bottom edge '
      'forward / top leaning aft 25-45 mm, within 3 mm of WT, aft normal down, 4 eye rays over the glass clear 81/81, 5 rays along both frame arms '
      'and under the glass bottom edge all end on the sight (0 gaps), 6 centred + mirror-symmetric',
      len(isl) == 1 and cdist <= 0.0015 and orient_ok and clear == 81 and not gaps and sym_ok,
      f'islands {len(isl)}' + (f' {bbs[:5]}' if len(isl) > 1 else '') + f'; worst glass corner {cdist * 1000:.1f} mm; lean {lean * 1000:.1f} mm, '
      f'WT bottom {db * 1000:.1f} / top {dt * 1000:.1f} mm, normal z {gn.z:.2f}; clear {clear}/{nclear}' + (f' e.g. {bad4[:3]}' if bad4 else '')
      + f'; gap rays {len(gaps)} of {nray} arm + {nfan} fan' + (f' e.g. {gaps[:4]}' if gaps else '') + f'; centre x {cx * 1000:.2f} mm, mirror {worst_m * 1000:.2f} mm')


def _rb(p, r, rng):
    """Cockpit.Joystick (Cockpit.cs:18): localEulerAngles = (pitch*range, 0, -roll*range), Unity Euler Z then X then Y; Unity (x,y,z) =
    Blender (x,z,y). Returns the 3x3 rotation in Blender space."""
    from mathutils import Matrix
    a = math.radians(p * rng)
    c = math.radians(-r * rng)
    Rx = Matrix(((1, 0, 0), (0, math.cos(a), -math.sin(a)), (0, math.sin(a), math.cos(a))))
    Rz = Matrix(((math.cos(c), -math.sin(c), 0), (math.sin(c), math.cos(c), 0), (0, 0, 1)))
    P = Matrix(((1, 0, 0), (0, 0, 1), (0, 1, 0)))
    return P @ Rx @ Rz @ P


def stick_sweep(R, rng=14.0, n=17, min_grip=0.010):
    """r8m (user review r8l: the stick base moved with the stick, a straight rod clipped through the front). cockpit_stick_base is a
    fixed part under fus_center; cockpit_stick (the Cockpit.Joystick transform, range 14) posed with the true game rotation over a
    17 x 17 pitch / roll grid touches nothing (every mesh except cockpit_stick*, canopy, pilot, stores), the grip clears the panel by
    >= 10 mm at full push, nothing goes under the floor top, no forward rod, the base stays on the floor aft of the bulkhead."""
    import a6m2_parts as AP
    zf = AP.cockpit_floor_z()
    st = bpy.data.objects.get('cockpit_stick')
    sb = bpy.data.objects.get('cockpit_stick_base')
    fails = []
    if st is None:
        R('r8m stick sweep: cockpit_stick present', False, 'missing')
        return
    G = st.matrix_world.translation.copy()
    if sb is None:
        fails.append('a: cockpit_stick_base missing')
    elif sb.parent is None or sb.parent.name != 'fus_center':
        fails.append(f'a: base parent {sb.parent.name if sb.parent else None}')
    if abs(G.x) > 0.005:
        fails.append(f'a: gimbal x {G.x:.4f}')
    sc = Scene(skip=('cockpit_stick', 'canopy_', 'pilot', 'store_', 'cockpit_eye'))
    vs, tris = _obj_tris(st)
    T = [t for t, m in tris]
    loc = [v - G for v in vs]
    hits, zmin, grip = [], 9.0, None
    for i in range(n):
        for j in range(n):
            p = -1 + 2 * i / (n - 1)
            r = -1 + 2 * j / (n - 1)
            Rm = _rb(p, r, rng)
            W = [G + Rm @ c for c in loc]
            ov = sc.tree.overlap(BVHTree.FromPolygons(W, T))
            if ov:
                hits.append((round(p, 3), round(r, 3), sorted({sc.meta[a][0] for a, _ in ov})))
            zmin = min(zmin, min(w.z for w in W))
            if abs(p - 1) < 1e-6 and abs(r) < 1e-6:
                grip = min(sc.tree.find_nearest(w)[3] for w in W if w.z > zf + 0.40)
    if hits:
        fails.append(f'b: {len(hits)} poses touch e.g. {hits[:4]}')
    if grip is None or grip < min_grip:
        fails.append(f'c: grip clearance at full push {grip}')
    if zmin < zf + 0.006:
        fails.append(f'd: lowest posed vertex zf{zmin - zf:+.4f}')
    fwd = max([v.y for v in vs] + ([(sb.matrix_world @ v.co).y for v in sb.data.vertices] if sb else []))
    if fwd > G.y + 0.07:
        fails.append(f'e: vertex {fwd - G.y:.3f} m forward of the gimbal (rod / tube)')
    if sb is not None:
        bw = [sb.matrix_world @ v.co for v in sb.data.vertices]
        if min(w.z for w in bw) < zf - 0.005 or max(w.y for w in bw) > -0.2414 - 0.010:
            fails.append(f'f: base bbox z {min(w.z for w in bw) - zf:+.4f} ymax {max(w.y for w in bw):.4f}')
    R(f'r8m stick sweep (user review r8l: base moved with the stick, rod through the front): fixed cockpit_stick_base under fus_center; '
      f'cockpit_stick at the true Joystick rotation (range {rng:g}, {n}x{n} pitch/roll) touches nothing, grip >= {min_grip * 1000:.0f} mm off the '
      f'panel at full push, above the floor, no forward rod',
      not fails, f'gimbal ({G.x:.3f}, {G.y:.3f}, zf+{G.z - zf:.3f}); hit poses {len(hits)}/{n * n}; grip at full push '
      f'{(grip if grip is not None else -1) * 1000:.1f} mm; lowest zf{zmin - zf:+.4f}; fwd {fwd - G.y:+.3f}' + (f'; FAIL {fails}' if fails else ''))


def throttle_sweep_clear(R, step=2, rng=40.0, min_lever_gap=0.010, min_wall_gap=0.003):
    """r8m (user review r8l: full throttle clipped through the levers). cockpit_throttle rotated about its own origin like
    Cockpit.Throttle (localEulerAngles.x = +throttle*40 in Unity = Blender rotation -deg about X: grip toward the nose), 0..40 deg every
    `step`: 1 no overlap with any other visible mesh (not *_int, gauge_*); 2 >= min_lever_gap from the mixture / prop-pitch /
    supercharger levers (ck_blue / navred knobs + their 'gear' shafts); 3 the grip moves >= 50 mm forward; 4 the knobs clear
    cockpit_walls / fus_center by >= min_wall_gap."""
    from mathutils import Matrix
    th = bpy.data.objects.get('cockpit_throttle')
    cs_ = bpy.data.objects.get('cockpit_consoles')
    if th is None or cs_ is None:
        R('r8m throttle sweep: cockpit_throttle / cockpit_consoles present', False, 'missing')
        return
    piv = th.matrix_world.translation.copy()
    tv, tt = _obj_tris(th)
    T = [t for t, m in tt]
    env = []
    for o in bpy.data.objects:
        if o.type != 'MESH' or o is th or o.name.endswith('_int') or o.name.startswith(('gauge_', 'pilot', 'store_', 'cockpit_eye')) or o.hide_render:
            continue
        bb = [o.matrix_world @ V(c) for c in o.bound_box]
        if not all(min(b[i] for b in bb) - 0.35 <= piv[i] <= max(b[i] for b in bb) + 0.35 for i in range(3)):
            continue
        v_, t_ = _obj_tris(o)
        env.append((o.name, BVHTree.FromPolygons(v_, [t for t, m in t_])))
    cv, ct = _obj_tris(cs_)
    lev = []
    for t, m in ct:
        c = (cv[t[0]] + cv[t[1]] + cv[t[2]]) / 3
        if m in ('ck_blue', 'navred') or (m == 'gear' and c.x < piv.x - 0.025 and 0.015 < c.y - piv.y < 0.12):
            lev.append(t)
    lt = BVHTree.FromPolygons(cv, lev) if lev else None
    lvs = sorted({i for t in lev for i in t})
    hits, gap_min, gap_at, gy = [], 9.0, None, {}
    degs = list(range(0, int(rng) + 1, step)) + ([rng] if int(rng) % step else [])
    for dg in degs:
        M = Matrix.Translation(piv) @ Matrix.Rotation(math.radians(-dg), 4, 'X') @ Matrix.Translation(-piv)
        W = [M @ v for v in tv]
        tb = BVHTree.FromPolygons(W, T)
        for nm, b in env:
            k = len(tb.overlap(b))
            if k:
                hits.append((dg, nm, k))
        if lt is not None:
            g = min(min(lt.find_nearest(w)[3] for w in W), min(tb.find_nearest(cv[i])[3] for i in lvs))
            if g < gap_min:
                gap_min, gap_at = g, dg
        gy[dg] = max(W, key=lambda w: w.z).y
    dy = gy[degs[-1]] - gy[0]
    wall = 9.0
    knobs = sorted({i for t, m in ct for i in t if m in ('ck_blue', 'navred')})
    for nm in ('cockpit_walls', 'fus_center'):
        o = bpy.data.objects.get(nm)
        if o is None or not knobs:
            continue
        v_, t_ = _obj_tris(o)
        b = BVHTree.FromPolygons(v_, [t for t, m in t_])
        wall = min(wall, min(b.find_nearest(cv[i])[3] for i in knobs))
    ok = not hits and lt is not None and gap_min >= min_lever_gap and dy >= 0.05 and wall >= min_wall_gap
    R(f'r8m throttle sweep (user review r8l: full throttle clipped the levers): cockpit_throttle at the true Throttle rotation 0..{rng:g} deg '
      f'(every {step}) overlaps nothing, >= {min_lever_gap * 1000:.0f} mm from the mixture / pitch / supercharger levers, grip moves forward, knobs '
      f'>= {min_wall_gap * 1000:.0f} mm off the wall',
      ok, f'overlaps {len(hits)}' + (f' e.g. {hits[:5]}' if hits else '') + f'; lever gap min {gap_min * 1000:.1f} mm at {gap_at} deg ({len(lev)} lever tris); '
      f'grip y {gy[0]:.3f} -> {gy[degs[-1]]:.3f} ({dy * 1000:+.0f} mm); knobs to wall {wall * 1000:.1f} mm')


def throttle_lever_one_piece(R, weld=0.0002):
    """r8n (user, r8m in game: the throttle handle was two rectangles with a visible gap where they joined). The cockpit_throttle lever
    (material 'gear', minus the pivot hub) must be ONE connected shell (vertices welded at `weld`, NO overlap merging) running from the
    pivot hub to the grip, closed (every edge on exactly 2 triangles: no open edges, no non-manifold edges), with no self-intersection
    between triangles that share no vertex (two butted / overlapping boxes intersect on the inside of the bend), outward-facing
    (positive signed volume). The r8m build fails 1 (2 shells) and 4."""
    th = bpy.data.objects.get('cockpit_throttle')
    if th is None:
        R('r8n throttle lever: cockpit_throttle present', False, 'missing')
        return
    vs, tt = _obj_tris(th)
    piv = th.matrix_world.translation.copy()
    G = [t for t, m in tt if m == 'gear']
    blk = [t for t, m in tt if m == 'ck_black']
    gc = sum((vs[i] for t in blk for i in t), V()) / max(1, 3 * len(blk)) if blk else None
    # weld (union-find on positions), then shells by shared welded vertices
    key = {}
    rep_ = {}
    for t in G:
        for i in t:
            k = tuple(round(c / weld) for c in vs[i])
            rep_[i] = key.setdefault(k, i)
    par = {}

    def f(i):
        par.setdefault(i, i)
        while par[i] != i:
            par[i] = par[par[i]]
            i = par[i]
        return i
    W = [tuple(rep_[i] for i in t) for t in G]
    for t in W:
        a = f(t[0]); par[f(t[1])] = a; par[f(t[2])] = a
    shells = {}
    for t in W:
        shells.setdefault(f(t[0]), []).append(t)
    # the lever = the shell whose vertex reaches farthest from the pivot; the hub shell stays within 20 mm of the pivot
    def reach(sh):
        return max((vs[i] - piv).length for t in sh for i in t)
    lever_shells = [sh for sh in shells.values() if reach(sh) > 0.025]
    lever = max(lever_shells, key=reach) if lever_shells else []
    near = min(((vs[i] - piv).length for t in lever for i in t), default=9.0)
    far = reach(lever) if lever else 0.0
    # closed manifold
    ec = {}
    for t in lever:
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            e = (min(a, b), max(a, b))
            ec[e] = ec.get(e, 0) + 1
    open_e = sum(1 for c in ec.values() if c == 1)
    nonman = sum(1 for c in ec.values() if c > 2)
    # self-intersection between non-adjacent triangles
    bt = BVHTree.FromPolygons(vs, lever) if lever else None
    selfx = 0
    if bt is not None:
        for a, b in bt.overlap(bt):
            if a < b and not (set(lever[a]) & set(lever[b])):
                selfx += 1
    vol = sum((vs[t[0]]).dot(vs[t[1]].cross(vs[t[2]])) for t in lever) / 6.0
    to_grip = (gc - piv).length if gc is not None else 0.0
    # the lever's far end sits in the black grip: its farthest vertex within 13 mm of the grip's surface
    bb_ = BVHTree.FromPolygons(vs, blk) if blk else None
    fv = max((i for t in lever for i in t), key=lambda i: (vs[i] - piv).length) if lever else None
    in_grip = bb_.find_nearest(vs[fv])[3] if (bb_ is not None and fv is not None) else 9.0
    ok = (len(lever_shells) == 1 and near <= 0.010 and gc is not None and in_grip <= 0.013 and open_e == 0 and nonman == 0
          and selfx == 0 and vol > 0)
    R('r8n throttle lever (user review r8m: the handle was two rectangles with a gap at the elbow): ONE closed shell from the pivot hub to the '
      'grip (welded 0.2 mm, no overlap merging), 0 open / non-manifold edges, no self-intersection, outward',
      ok, f'lever shells {len(lever_shells)} (gear shells {len(shells)}); lever {len(lever)} tris spans {near * 1000:.1f} .. {far * 1000:.1f} mm '
      f'from the pivot (grip centre {to_grip * 1000:.1f} mm, lever end {in_grip * 1000:.1f} mm from the grip surface); open edges {open_e}, non-manifold {nonman}, self-intersecting pairs {selfx}, '
      f'volume {vol * 1e6:.2f} cm3')


# =============================================================================================== r8o: open break ends, stock-style internals
# User test of r8n (11-21): every break showed a SOLID round metal disc ('structure' fan caps / wing metal_dark caps); a 'box' in the same
# metal texture through the damage holes ahead of the cockpit (the fuselage tank, a 'structure' box). Stock breaks are open (no cap, frames
# set back, stubs); stock draws aircraft_structure only on thin members / bay walls and has no tank meshes.
R8O_INNER = ('interior',)


class _Part:
    """world triangles of one object: verts, tris, mats, normals, areas, centroids, + a paint BVH."""
    def __init__(self, o):
        self.name = o.name
        vs, tl = _obj_tris(o)
        self.vs = vs
        self.tris = [t for t, _ in tl]
        self.mats = [m for _, m in tl]
        self.nrm, self.area, self.cen = [], [], []
        for t in self.tris:
            a, b, c = (vs[i] for i in t)
            n = (b - a).cross(c - a)
            self.area.append(n.length / 2)
            self.nrm.append(n.normalized() if n.length > 1e-14 else V((0, 0, 0)))
            self.cen.append((a + b + c) / 3)
        pv = [k for k, m in enumerate(self.mats) if m == 'paint']
        self.paint = BVHTree.FromPolygons(vs, [self.tris[k] for k in pv]) if pv else None

    def skin_dist(self, p):
        if self.paint is None:
            return 9.0
        h = self.paint.find_nearest(p)
        return h[3] if h[0] is not None else 9.0

    def skin_normal(self, p):
        h = self.paint.find_nearest(p) if self.paint else (None,)
        return h[1] if h[0] is not None else None


def r8o_breaks():
    """every break end: (key, part, plane point, unit normal OUT of the part through the plane, setback of its rib / frame)."""
    import a6m2_parts as AP
    import a6m2_spec as S
    K = S.K
    ye, yr, yt = S.ENGINE_AFT_Y * K, S.REAR_FWD_Y * K, S.TAIL_FWD_Y * K
    out = []
    for key, part, y, sg in (('fus 0.955 aft end', 'fus_engine', ye, -1), ('fus 0.955 front end', 'fus_center', ye, 1),
                             ('fus -2.715 aft end', 'fus_center', yr, -1), ('fus -2.715 front end', 'fus_rear', yr, 1),
                             ('fus -4.143 aft end', 'fus_rear', yt, -1), ('fus -4.143 front end', 'fus_tail', yt, 1)):
        out.append((key, part, V((0, y, 0)), V((0, sg, 0)), 0.10))
    br = [S.span_built(b) for b in S.WING_BREAKS[:3]]
    for side, L in ((1, 'R'), (-1, 'L')):
        for k, (inb, outb) in enumerate((('fus_center', f'wing_inner_{L}'), (f'wing_inner_{L}', f'wing_mid_{L}'), (f'wing_mid_{L}', f'wing_tip_{L}'))):
            p0, n = AP.wing_break_plane(side, br[k])
            out.append((f'wing {L} br{k} outboard end', inb, p0, n, 0.10))
            out.append((f'wing {L} br{k} root end', outb, p0, -n, 0.10))
        out.append((f'stab {L} root', f'stab_{L}', V((0, 0, 0)), V((-side, 0, 0)), 0.06))
    z0 = S.FIN[0][0] * K
    out.append(('fin root', 'fin', V((0, 0, z0)), V((0, 0, -1)), 0.06))
    return out


def _parts(names):
    return {n: _Part(bpy.data.objects[n]) for n in names if n in bpy.data.objects}


def _plane_basis(n):
    ref = V((0, 0, 1)) if abs(n.z) < 0.9 else V((1, 0, 0))
    u = (ref - n * ref.dot(n)).normalized()
    return u, n.cross(u)


def _slice(P, p0, n, d):
    """segments (2D in the plane basis) of the part's paint skin cut by the plane d inside (p0 - n d)."""
    q0 = p0 - n * d
    u, w = _plane_basis(n)
    segs = []
    for k, t in enumerate(P.tris):
        if P.mats[k] != 'paint':
            continue
        a, b, c = (P.vs[i] for i in t)
        da, db, dc = (a - q0).dot(n), (b - q0).dot(n), (c - q0).dot(n)
        pts = []
        for (p, dp), (q, dq) in (((a, da), (b, db)), ((b, db), (c, dc)), ((c, dc), (a, da))):
            if (dp < 0) != (dq < 0):
                x = p + (q - p) * (dp / (dp - dq))
                pts.append(((x - q0).dot(u), (x - q0).dot(w)))
        if len(pts) == 2:
            segs.append(pts)
    return segs, u, w


def _inside2(segs, x, y):
    cr = 0
    for (ax, ay), (bx, by) in segs:
        if (ay > y) != (by > y):
            xi = ax + (y - ay) * (bx - ax) / (by - ay)
            if xi > x:
                cr += 1
    return cr % 2 == 1


def _segdist2(segs, x, y):
    best = 9.0
    for (ax, ay), (bx, by) in segs:
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 < 1e-16 else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / L2))
        best = min(best, math.hypot(x - ax - t * dx, y - ay - t * dy))
    return best


def _struct_regions(P, ang=5.0, plane_tol=0.002, weld=1e-4):
    """coplanar connected 'structure' regions of a part: list of (area, perimeter, w_eff, tri indices)."""
    key = lambda v: (round(v.x / weld), round(v.y / weld), round(v.z / weld))
    ids = {}
    vid = [ids.setdefault(key(v), len(ids)) for v in P.vs]
    st = [k for k, m in enumerate(P.mats) if m == 'structure' and P.area[k] > 1e-10]
    emap = {}
    for k in st:
        a, b, c = (vid[i] for i in P.tris[k])
        for e in ((a, b), (b, c), (c, a)):
            emap.setdefault((min(e), max(e)), []).append(k)
    cosA = math.cos(math.radians(ang))
    seen = set()
    regs = []
    pos = {}
    for i, v in enumerate(P.vs):
        pos.setdefault(vid[i], v)
    for k0 in st:
        if k0 in seen:
            continue
        n0 = P.nrm[k0]; d0 = n0.dot(P.cen[k0])
        reg = [k0]; seen.add(k0); stack = [k0]
        while stack:
            k = stack.pop()
            a, b, c = (vid[i] for i in P.tris[k])
            for e in ((a, b), (b, c), (c, a)):
                for k2 in emap.get((min(e), max(e)), ()):
                    if k2 in seen:
                        continue
                    if P.nrm[k2].dot(n0) < cosA or abs(P.nrm[k2].dot(P.cen[k2]) - d0) > plane_tol:
                        continue
                    seen.add(k2); reg.append(k2); stack.append(k2)
        A = sum(P.area[k] for k in reg)
        ecount = {}
        for k in reg:
            t = P.tris[k]
            for i, j in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
                e = (min(vid[i], vid[j]), max(vid[i], vid[j]))
                ecount[e] = ecount.get(e, 0) + 1
        per = 0.0
        for e, c in ecount.items():
            if c == 1:
                per += (pos[e[0]] - pos[e[1]]).length
        regs.append((A, per, 2 * A / per if per > 1e-9 else 0.0, reg))
    return regs


def _components(P, mat, weld=1e-4):
    """connected components of one material (welded): list of (closed, signed volume, tri indices)."""
    key = lambda v: (round(v.x / weld), round(v.y / weld), round(v.z / weld))
    ids = {}
    vid = [ids.setdefault(key(v), len(ids)) for v in P.vs]
    ks = [k for k, m in enumerate(P.mats) if m == mat]
    parent = {}

    def f(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for k in ks:
        a, b, c = (vid[i] for i in P.tris[k])
        parent[f(a)] = f(b); parent[f(b)] = f(c)
    groups = {}
    for k in ks:
        groups.setdefault(f(vid[P.tris[k][0]]), []).append(k)
    out = []
    for g in groups.values():
        ec = {}
        vol = 0.0
        for k in g:
            t = P.tris[k]
            a, b, c = (P.vs[i] for i in t)
            vol += a.dot(b.cross(c)) / 6.0
            for i, j in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
                e = (min(vid[i], vid[j]), max(vid[i], vid[j]))
                ec[e] = ec.get(e, 0) + 1
        closed = all(c == 2 for c in ec.values())
        out.append((closed, vol, g))
    return out


DEEP_WALL_REACH = 0.50     # r8o round 3: C11 / C3 coverage look this far into every break end (round 2 stopped at 0.15 m)
DEEP_WALL_COVER = 0.60     # C11: a plane seen first by more of the axial rays than this is a full-section wall
# The documented exceptions (intended walls): (break-key prefix, material, minimum depth m, reason). 'structure' is never allowed, and an
# allowed wall must be at least the stated depth in and >= 90 % its material (a plain wall, no light stiffener lattice on its face).
DEEP_WALL_ALLOW = (
    ('fus 0.955 aft end', 'metal_dark', 0.35, 'the firewall: plain dark plate 0.38 m in, behind the open end frame and the engine-mount truss'),
    ('wing ', 'interior', 0.25, 'bay-end wall of the lined wing cavity in the liner paint (round 2; stock: first full rib 0.4 m or more in)'),
    ('stab ', 'interior', 0.25, 'bay-end wall of the lined stab root cavity (TAIL_CAVITY 0.30 m), liner paint'),
    ('fin root', 'interior', 0.25, 'bay-end wall of the lined fin root cavity (TAIL_CAVITY 0.30 m), liner paint'),
)


def deep_wall_allowed(key, mat, depth, mix):
    """C11: the reason when this wall is a documented exception, else None."""
    for pre, m_, dmin, why in DEEP_WALL_ALLOW:
        if key.startswith(pre) and mat == m_ and mat != 'structure' and depth >= dmin and mix.get(m_, 0) >= 0.90:
            return why
    return None


def r8o_checks(R, label=''):
    """C1-C8, C10, C11 of the r8o design (C9 lives in check_a6m2_model.see_through). Returns the measured numbers (also for the r8n baseline run)."""
    import a6m2_internals as AI
    import a6m2_spec as S
    import a6m2_parts as AP
    breaks = r8o_breaks()
    P = _parts(sorted({b[1] for b in breaks}))
    meas = {}
    cos30 = math.cos(math.radians(30))
    # ---------------------------------------------------------------------------------- C1 break_flat
    flat = {}
    for key, pn, p0, n, sb in breaks:
        Pt = P.get(pn)
        if Pt is None:
            continue
        A = 0.0
        bym = {}
        for k, t in enumerate(Pt.tris):
            m = Pt.mats[k]
            if m == 'paint' or Pt.area[k] < 1e-12:
                continue
            if abs(Pt.nrm[k].dot(n)) < cos30:
                continue
            if any(abs((Pt.vs[i] - p0).dot(n)) > 0.012 for i in t):
                continue
            if Pt.skin_dist(Pt.cen[k]) <= 0.010:
                continue
            A += Pt.area[k]; bym[m] = bym.get(m, 0.0) + Pt.area[k]
        flat[key] = (round(A, 4), {m: round(a, 3) for m, a in bym.items()})
    worst = max(flat.items(), key=lambda kv: kv[1][0])
    meas['C1'] = flat
    R(f'{label}r8o C1 break_flat (user test r8n: a SOLID metal disc closed every break): at every break end the non-paint faces lying in the '
      'plane (all vertices within 12 mm, normal within 30 deg of the axis) more than 10 mm inside the skin sum to <= 0.03 m2',
      all(v[0] <= 0.03 for v in flat.values()), f'{len(flat)} ends, worst {worst[0]} {worst[1][0]} m2 {worst[1][1]}; '
      + ', '.join(f'{k} {v[0]}' for k, v in flat.items() if v[0] > 0.001))
    # ---------------------------------------------------------------------------------- C2 break_see_into
    kids = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith(('cockpit_', 'gauge_'))]
    see = {}
    walls = {}
    bad2 = []
    bad10 = []
    for key, pn, p0, n, sb in breaks:
        Pt = P.get(pn)
        if Pt is None:
            continue
        objs = [bpy.data.objects[pn]] + (kids if pn == 'fus_center' else [])
        Vs, Fs, Fm = [], [], []
        for o in objs:
            vs_, tl_ = _obj_tris(o)
            b0 = len(Vs); Vs += vs_; Fs += [tuple(i + b0 for i in t) for t, _ in tl_]; Fm += [m for _, m in tl_]
        tree = BVHTree.FromPolygons(Vs, Fs)
        segs, u, w = _slice(Pt, p0, n, 0.03)
        if not segs:
            continue
        xs_ = [c for s_ in segs for c, _ in s_]; ys_ = [c for s_ in segs for _, c in s_]
        far, near, tot = 0, 0, 0
        planes = {}
        scov = 0
        deep = {}                           # r8o round 3 C11: (normal key, plane offset slab) -> [count, {material: count}, depth sum]
        step = 0.015
        x = min(xs_)
        d_far, d_near = 0.08, 0.05          # r8o round 2: the stab / fin roots too (round 1 relaxed them to 0.05 / 0.03 for the full rib at 0.06)
        while x <= max(xs_):
            y = min(ys_)
            while y <= max(ys_):
                if _inside2(segs, x, y) and _segdist2(segs, x, y) > 0.020:
                    q = p0 + u * x + w * y
                    o_ = q + n * 0.5
                    d = -n
                    dep = 9.0
                    pp = o_
                    for _ in range(40):
                        h = tree.ray_cast(pp, d, 5.0)
                        if h[0] is None:
                            break
                        if h[1].dot(d) < 0:
                            dep = (q - h[0]).dot(n)
                            if Fm[h[2]] == 'structure' and dep <= DEEP_WALL_REACH:
                                scov += 1                               # C3 projected coverage: structure seen head-on from the break
                                # (round 3: within DEEP_WALL_REACH 0.5 m; round 2 stopped at 0.15 m and the 0.17 m firewall lattice escaped it)
                            nh = h[1].normalized()
                            if Fm[h[2]] != 'paint' and abs(nh.dot(n)) >= math.cos(math.radians(10)) and dep <= DEEP_WALL_REACH:
                                if nh.dot(n) < 0:
                                    nh = -nh
                                kd = (round(nh.x * 10), round(nh.y * 10), round(nh.z * 10), round(nh.dot(h[0]) / 0.006))
                                e_ = deep.setdefault(kd, [0, {}, 0.0])
                                e_[0] += 1; e_[1][Fm[h[2]]] = e_[1].get(Fm[h[2]], 0) + 1; e_[2] += dep
                            if abs(h[1].normalized().dot(n)) >= math.cos(math.radians(5)) and dep <= 0.15:
                                kp = round(dep / 0.004)                 # one plane across the axis (4 mm slab)
                                planes[kp] = planes.get(kp, 0) + 1
                            break
                        pp = h[0] + d * 1e-5
                    tot += 1
                    far += dep >= d_far
                    near += dep < d_near
                y += step
            x += step
        if tot:
            pm = 0
            for kp in planes:                                           # a plane may straddle two 4 mm slabs: best adjacent pair
                pm = max(pm, planes[kp] + planes.get(kp + 1, 0))
            see[key] = (tot, round(far / tot, 3), round(near / tot, 3), round(pm / tot, 3), round(scov / tot, 3))
            # C11: one plane (any non-paint material, same normal, offset within two 6 mm slabs) seen first by > 60 % of the axial rays
            best = None
            for kd, (c_, mm, dsum) in deep.items():
                c2 = c_
                mm2 = dict(mm)
                ds2 = dsum
                nb = deep.get(kd[:3] + (kd[3] + 1,))
                if nb:
                    c2 += nb[0]; ds2 += nb[2]
                    for m_, v_ in nb[1].items():
                        mm2[m_] = mm2.get(m_, 0) + v_
                if best is None or c2 > best[0]:
                    best = (c2, mm2, ds2 / max(c2, 1))
            if best is not None:
                mat_ = max(best[1].items(), key=lambda kv: kv[1])[0]
                walls[key] = (round(best[0] / tot, 3), round(best[2], 3), mat_, {m_: round(v_ / best[0], 2) for m_, v_ in best[1].items()})
            if far / tot < 0.60 or near / tot > 0.15:
                bad2.append(key)
            if pm / tot > 0.30:
                bad10.append(key)
    meas['C2'] = see
    R(f'{label}r8o C2 break_see_into (stock: one looks into a hollow shell): rays along the axis through a 15 mm grid inside every break ring: '
      '>= 60 % travel >= 0.08 m past the plane before the first front face, <= 15 % hit within 0.05 m (every end, the stab / fin roots too)',
      not bad2 and see, f'bad {bad2}; ' + ', '.join(f'{k} n{v[0]} far {v[1]} near {v[2]}' for k, v in see.items()))
    # ---------------------------------------------------------------------------------- C11 break_deep_wall (round 3)
    bad11, allowed11 = [], []
    for key, (cv, dp, mat_, mix) in walls.items():
        if cv <= DEEP_WALL_COVER:
            continue
        why = deep_wall_allowed(key, mat_, dp, mix)
        (allowed11 if why else bad11).append(f'{key} {cv:.2f} at {dp:.2f} m {mat_}' + (f' [{why}]' if why else ''))
    meas['C11'] = (walls, allowed11, bad11)
    R(f'{label}r8o C11 break_deep_wall (review of r8o round 2: the firewall disc sat 0.17 m in, 2 cm past the 0.15 m windows of C3 / C10): '
      f'at every break end no single plane across the axis - any non-paint material, metal_dark and interior included - is the first hit '
      f'of > {int(DEEP_WALL_COVER * 100)} % of the axial rays within {DEEP_WALL_REACH} m of the break, except the documented DEEP_WALL_ALLOW walls',
      not bad11 and walls, f'over, not allowed: {bad11}; allowed: {allowed11}; max plane per end: '
      + ', '.join(f'{k} {v[0]}@{v[1]}{v[2][:2]}' for k, v in walls.items()))
    R(f'{label}r8o C10 break_one_plane (review of r8o round 1: 84-94 % of the axial rays into every wing / stab / fin end stopped on ONE rib '
      'plane): at every break end <= 30 % of the axial rays have their first hit on one plane across the axis within 0.15 m of the break',
      not bad10 and see, f'bad {bad10}; ' + ', '.join(f'{k} {v[3]}' for k, v in see.items()))
    # ---------------------------------------------------------------------------------- C3 struct_no_plate / C4 struct_no_volume
    allp = _parts([o.name for o in bpy.data.objects if o.type == 'MESH' and o.data.materials and any(m and m.name == 'structure' for m in o.data.materials)])
    wmax = {}
    regmap = {}
    plates = []
    for n_, Pt in allp.items():
        regs = _struct_regions(Pt)
        if not regs:
            continue
        top = max(regs, key=lambda r_: r_[2])
        wmax[n_] = round(top[2], 3)
        for A, per, we, reg in regs:
            for k in reg:
                regmap[(n_, k)] = we
            if we > 0.25:
                c = sum((Pt.cen[k] for k in reg), V()) / len(reg)
                plates.append(f'{n_} w_eff {we:.2f} A {A:.3f} at ({c.x:.2f},{c.y:.2f},{c.z:.2f})')
    # r8o round 2 (review: the round-1 two-web rib passed as separate strips, w_eff 0.246 each, and still read as one solid plate): every
    # PLANE of structure faces - normals within ~3 deg, offset within 4 mm, connected or not - is rasterised (5 mm cells) and its union
    # measured: w_eff = 2 A / perimeter of the union
    umax = {}
    for n_, Pt in allp.items():
        bins = {}
        for k, m in enumerate(Pt.mats):
            if m != 'structure' or Pt.area[k] < 1e-9:
                continue
            nn = Pt.nrm[k]
            if nn.length < 0.5:
                continue
            if (nn.x, nn.y, nn.z) < (0, 0, 0):
                nn = -nn                                                # both faces of a thin plate fall in one plane bin
            if n_.startswith(('wing_inner', 'wing_mid')) and abs(nn.y) > 0.95:
                continue                    # the two spanwise spar webs (full-depth webs at the spars, as the review allows; edge-on from a break)
            key = (round(nn.x * 20), round(nn.y * 20), round(nn.z * 20), round(nn.dot(Pt.cen[k]) / 0.004))
            bins.setdefault(key, []).append(k)
        merged = {}
        for key, ks in bins.items():                                    # adjacent offset slabs of one normal belong together
            base = key[:3]
            merged.setdefault(base, {}).setdefault(key[3], []).extend(ks)
        for base, slabs in merged.items():
            done = set()
            for o_ in sorted(slabs):
                if o_ in done:
                    continue
                grp = []
                q_ = o_
                while q_ in slabs:
                    grp += slabs[q_]; done.add(q_); q_ += 1
                A0 = sum(Pt.area[k] for k in grp)
                if A0 < 0.03:
                    continue
                nrm = sum((Pt.nrm[k] * (1 if Pt.nrm[k].dot(Pt.nrm[grp[0]]) > 0 else -1) for k in grp), V()).normalized()
                u_, w_ = _plane_basis(nrm)
                cells = set()
                h_ = 0.005
                for k in grp:
                    a, b, c = (Pt.vs[i] for i in Pt.tris[k])
                    P2 = [(p.dot(u_), p.dot(w_)) for p in (a, b, c)]
                    xs2 = [p[0] for p in P2]; ys2 = [p[1] for p in P2]
                    for ix in range(int(math.floor(min(xs2) / h_)), int(math.floor(max(xs2) / h_)) + 1):
                        for iy in range(int(math.floor(min(ys2) / h_)), int(math.floor(max(ys2) / h_)) + 1):
                            px, py = (ix + 0.5) * h_, (iy + 0.5) * h_
                            d1 = (P2[1][0] - P2[0][0]) * (py - P2[0][1]) - (P2[1][1] - P2[0][1]) * (px - P2[0][0])
                            d2 = (P2[2][0] - P2[1][0]) * (py - P2[1][1]) - (P2[2][1] - P2[1][1]) * (px - P2[1][0])
                            d3 = (P2[0][0] - P2[2][0]) * (py - P2[2][1]) - (P2[0][1] - P2[2][1]) * (px - P2[2][0])
                            if (d1 >= 0 and d2 >= 0 and d3 >= 0) or (d1 <= 0 and d2 <= 0 and d3 <= 0):
                                cells.add((ix, iy))
                if not cells:
                    continue
                A = len(cells) * h_ * h_
                per = sum(1 for (ix, iy) in cells for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)) if (ix + dx, iy + dy) not in cells) * h_
                we = 2 * A / per if per > 0 else 0.0
                umax[n_] = max(umax.get(n_, 0.0), round(we, 3))
                if we > 0.25:
                    c = sum((Pt.cen[k] for k in grp), V()) / len(grp)
                    plates.append(f'{n_} union w_eff {we:.2f} A {A:.3f} at ({c.x:.2f},{c.y:.2f},{c.z:.2f})')
                for k in grp:
                    regmap[(n_, k)] = max(regmap.get((n_, k), 0.0), we)
    cov = {k: v[4] for k, v in see.items()}
    cov_bad = [k for k, v in cov.items() if v > 0.30]
    meas['C3'] = (wmax, umax, cov)
    R(f'{label}r8o C3 struct_no_plate (stock aircraft_structure only on thin members): every coplanar connected structure region AND the '
      'union of every plane of structure faces (connected or not, 5 mm raster) has w_eff = 2 A / perimeter <= 0.25 m, and seen head-on '
      'from every break end structure within 0.5 m (round 3; round 2: 0.15 m) covers <= 30 % of the section (projected: first axial hits; r8o round 1 84-94 %)',
      not plates and not cov_bad, f'over: {plates[:6]}; coverage over 30 %: {cov_bad}; max per part connected {wmax}; union {umax}; '
      f'coverage {cov}')
    vols = []
    for n_, Pt in allp.items():
        for closed, vol, g in _components(Pt, 'structure'):
            if closed and vol > 0.005:
                c = sum((Pt.cen[k] for k in g), V()) / len(g)
                vols.append(f'{n_} {vol:.4f} m3 at ({c.x:.2f},{c.y:.2f},{c.z:.2f})')
    meas['C4'] = vols
    R(f'{label}r8o C4 struct_no_volume (r8n: the tank boxes, firewall and oil tank were structure solids): no closed structure component '
      'encloses > 0.005 m3', not vols, f'{len(vols)} {vols[:6]}')
    # ---------------------------------------------------------------------------------- C5 tanks_material
    tank_parts = {'fus_center': 'fus_tank', 'fus_engine': 'oil_tank', 'wing_inner_L': 'wing_tank_L', 'wing_inner_R': 'wing_tank_R'}
    TP = _parts(list(tank_parts))
    wrong = {}
    ncomp = {}
    clear = {}
    tanks = AI.TANKS if AI.TANKS else [('fus_tank', 'fus_center', (0.0, 0.10 * S.K, 0.22), (0.28, 0.29, 0.20)),
                                        ('oil_tank', 'fus_engine', (0.0, 1.18 * S.K, 0.28), (0.22, 0.12, 0.12))]
    for nm, pn, c, h in tanks:
        Pt = TP.get(pn)
        if Pt is None:
            continue
        c = V(c)
        lo_, hi_ = c - V(h) - V((0.002, 0.002, 0.002)), c + V(h) + V((0.002, 0.002, 0.002))
        inb = lambda p: all(lo_[i] <= p[i] <= hi_[i] for i in range(3))
        for k, t in enumerate(Pt.tris):
            if inb(Pt.cen[k]) and Pt.mats[k] not in ('tank', 'metal_dark'):
                wrong[f'{nm}:{Pt.mats[k]}'] = wrong.get(f'{nm}:{Pt.mats[k]}', 0) + 1
        comps = [g for closed, vol, g in _components(Pt, 'tank') if inb(sum((Pt.cen[k] for k in g), V()) / len(g))]
        ncomp[nm] = len(comps)
        if nm == 'fus_tank' and comps:
            others = []
            for o in [bpy.data.objects[pn]] + kids:
                vs_, tl_ = _obj_tris(o)
                b0 = len(others)
                others += [(vs_[t[0]], vs_[t[1]], vs_[t[2]]) for t, m in tl_ if m != 'tank' and not (m == 'metal_dark' and inb((vs_[t[0]] + vs_[t[1]] + vs_[t[2]]) / 3))]
            Vo = [p for tri in others for p in tri]
            ot = BVHTree.FromPolygons(Vo, [(3 * i, 3 * i + 1, 3 * i + 2) for i in range(len(others))])
            tv = [Pt.vs[i] for g in comps for k in g for i in Pt.tris[k]]
            dmin = min(ot.find_nearest(p)[3] for p in tv[::3])
            clear[nm] = round(dmin, 4)
    meas['C5'] = (wrong, ncomp, clear)
    okc = all(ncomp.get(t, 0) >= 1 for t in ('fus_tank', 'oil_tank', 'wing_tank_L', 'wing_tank_R'))
    R(f'{label}r8o C5 tanks_material (user test r8n: a "box" in the structure texture through the damage holes): every face inside the fuselage, '
      'oil and wing tank bounds is tank metal or a dark strap, >= 1 tank cell in fus_center, fus_engine and each wing_inner, fuselage tank '
      '>= 15 mm clear of the skin / guns / cockpit', not wrong and okc and all(v >= 0.015 for v in clear.values()),
      f'wrong faces {wrong}; tank cells {ncomp}; fus tank clearance {clear} m')
    # ---------------------------------------------------------------------------------- C6 internals_in_own_part
    viol = []
    guns = set()
    stub_min = 9.0
    tank_min = 9.0
    for key, pn, p0, n, sb in breaks:
        Pt = P.get(pn)
        if Pt is None:
            continue
        for k, t in enumerate(Pt.tris):
            m = Pt.mats[k]
            if m in ('paint', 'interior'):
                continue
            if m not in ('structure', 'tank', 'metal_dark', 'gear', 'ck_dark'):
                continue                                    # ('well' / 'well_dark': the wells' and flap coves' own walls, exterior)
            ds = [(Pt.vs[i] - p0).dot(n) for i in t]
            dmax = max(ds)
            if key.startswith('wing') or key.startswith(('stab', 'fin')):
                # the wing plane is infinite: count only faces within the section's reach of the plane
                if min(abs(d_) for d_ in ds) > 0.60:
                    continue
            elif key.startswith('fus'):
                c_ = Pt.cen[k]                              # fuselage planes: inside the body section only (the chin scoop,
                zt_, zb_ = AP.body_params(c_.y)[0], AP.body_params(c_.y)[1]       # exhausts, wing and fillet are exterior)
                if not (zb_ + 0.004 < c_.z < zt_ - 0.004 and abs(c_.x) < AP.body_ring_x(c_.y, c_.z) - 0.004):
                    continue
            if m == 'structure':
                stub_min = min(stub_min, -dmax)
                if dmax > -0.015 + 1e-4:
                    viol.append(f'{key}: structure {dmax * 1000:+.1f} mm')
            elif m == 'tank':
                tank_min = min(tank_min, -dmax)
                if dmax > -0.10 + 1e-4:
                    viol.append(f'{key}: tank {dmax * 1000:+.1f} mm')
            elif dmax > 0.0005:
                c_ = Pt.cen[k]
                if m == 'metal_dark' and pn == 'fus_engine' and abs(abs(c_.x) - S.TROUGH_X * S.K) < 0.04 and c_.z > 0.40:
                    guns.add(f'{dmax * 1000:+.0f}')         # the Type 97 barrels run from the troughs back to the receivers (exterior guns)
                    continue
                viol.append(f'{key}: {m} {dmax * 1000:+.1f} mm')
    meas['C6'] = (stub_min, tank_min)
    vs6 = sorted(set(viol))
    R(f'{label}r8o C6 internals_in_own_part (r8n: the wing tank stood 94 mm through the root break): no internal vertex past its part\'s '
      'break planes; structure (stubs, spars, longerons) ends >= 15 mm short, tanks / frames >= 0.10 m inside',
      not vs6, f'{len(vs6)} {vs6[:8]}; nearest structure {stub_min * 1000:.1f} mm, tank {tank_min * 1000:.1f} mm inside; '
      f'not counted: the Type 97 barrels of fus_engine reach {max(guns, key=float) if guns else 0} mm past the cowl joint to the receivers')
    # ---------------------------------------------------------------------------------- C7 hole_view_fwd
    hv = _parts(['fus_center', 'fus_engine'])
    Vs, Fs, meta = [], [], []
    for o in [bpy.data.objects['fus_center'], bpy.data.objects['fus_engine']] + kids:
        vs_, tl_ = _obj_tris(o)
        b0 = len(Vs); Vs += vs_
        for k, (t, m) in enumerate(tl_):
            Fs.append(tuple(i + b0 for i in t)); meta.append((o.name, m, k))
    tree = BVHTree.FromPolygons(Vs, Fs)
    pv, pf = [], []
    for nm_ in ('fus_center', 'fus_engine'):
        Pt = hv[nm_]
        b0 = len(pv); pv += Pt.vs
        pf += [tuple(i + b0 for i in t) for k, t in enumerate(Pt.tris) if Pt.mats[k] == 'paint']
    ptree = BVHTree.FromPolygons(pv, pf)
    cls = {}
    big = 0
    nrays = 0
    x = -0.60
    while x <= 0.60 + 1e-9:
        y = -0.30
        while y <= 1.10 + 1e-9:
            h = ptree.ray_cast(V((x, y, 2.0)), V((0, 0, -1)), 3.0)
            if h[0] is not None and h[0].z > 0 and h[1].z > 0.05:
                nn = h[1].normalized()
                d = -nn
                pp = h[0] + d * 0.0005
                for _ in range(40):
                    g = tree.ray_cast(pp, d, 3.0)
                    if g[0] is None:
                        break
                    ob, m, k = meta[g[2]]
                    if m == 'paint' or g[1].dot(d) >= 0:
                        pp = g[0] + d * 1e-5
                        continue
                    nrays += 1
                    cls[m] = cls.get(m, 0) + 1
                    if m == 'structure' and regmap.get((ob, k), 0.0) > 0.25:
                        big += 1
                    break
            y = round(y + 0.02, 4)
        x = round(x + 0.02, 4)
    sfrac = cls.get('structure', 0) / max(nrays, 1)
    meas['C7'] = (nrays, round(sfrac, 3), dict(sorted(cls.items(), key=lambda kv: -kv[1])), big)
    R(f'{label}r8o C7 hole_view_fwd (user test r8n: the "box" through the holes): rays into the upper forward fuselage (y -0.30..1.10, '
      'z > 0, 20 mm grid, skin + inner skin removed = HP 0 holes): structure <= 25 % of the first hits, none on a structure plate (w_eff > 0.25)',
      sfrac <= 0.25 and big == 0, f'{nrays} hits, structure {sfrac * 100:.1f} %, on plates {big}; by material {meas["C7"][2]}')
    # ---------------------------------------------------------------------------------- C8 seam_dark
    lit = {}
    tot8 = 0
    for key, pn, p0, n, sb in breaks:
        Pt = P.get(pn)
        if Pt is None:
            continue
        for k, t in enumerate(Pt.tris):
            m = Pt.mats[k]
            if m in ('paint', 'well', 'well_dark') or Pt.area[k] < 1e-10:
                continue                                    # (the well / leg-slot walls are the opening's own walls)
            ds = [(Pt.vs[i] - p0).dot(n) for i in t]
            if max(ds) > 0.0005 or min(ds) < -0.0255:
                continue
            c = Pt.cen[k]
            hs = Pt.paint.find_nearest(c) if Pt.paint else (None,)
            if hs[0] is None or hs[3] > 0.016 or (c - hs[0]).dot(hs[1]) > 0:
                continue                                    # the lining: inside the skin, within 16 mm of it
            inplane = max(abs(d_) for d_ in ds) < 0.001
            sn = hs[1]
            if not inplane and (sn is None or abs(sn.normalized().dot(Pt.nrm[k])) < 0.7):
                continue
            tot8 += 1
            if m != 'metal_dark':
                kk = f'{key}:{m}'
                lit[kk] = lit.get(kk, 0) + 1
    meas['C8'] = (tot8, lit)
    R(f'{label}r8o C8 seam_dark (r8g / 1.9.13 seam backing): at every joint the lining within 25 mm of the plane (inner-skin band, wing '
      'liner band, skin edge) is 100 % metal_dark', tot8 > 0 and not lit, f'{tot8} lining faces; not dark {lit}')
    return meas
