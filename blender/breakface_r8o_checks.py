"""Generic break-face checks (2026-11-22), the r8o checks_r8 C1 / C6 / C8 / C10 / C11 ported to any of our aircraft.

User (after the r8o damage check, where every break face had been closed by a SOLID metal disc - "dividers"): "The Nimrod and
FD-32 need to be changed as well, I thought both of those had been previously fixed". The fix (open break ends with set-back open
frames / cap strips, a dark seam band at every liner end, stubs short of the plane, deep bay-end walls) is guarded here:

  C1  break_flat      at every break end the non-paint faces lying in the plane (all vertices within 12 mm, normal within 30 deg of
                      the axis) more than 10 mm inside the skin sum to <= 0.03 m2 (a disc / cap in the plane)
  C10 break_one_plane <= 30 % of the axial rays (15 mm grid inside the section) have their first front-face hit on ONE plane across the
                      axis within 0.15 m (a full rib / bulkhead just behind the plane)
  C11 break_deep_wall no single non-paint plane across the axis is the first hit of > 60 % of the axial rays within 0.5 m, except the
                      documented walls (cockpit walls, bay-end walls in the liner paint, firewalls well back) - never 'structure'
  C12 cockpit_wall_relief (round 2, 2026-11-27) a wall allowed by C11 with a relief rule (the cockpit walls) must be dark, cover <= max_cover
                      of the view and have structure (frames, longerons, stringers) in front of it on >= min_relief of the rays
  C8  seam_dark       the lining within 25 mm of the plane (inner skin / liner band, skin edge strips) is dark (seam backing present)
  C6  stubs_short     no 'structure' vertex inside the section within 15 mm of the plane or past it (stubs end short of the plane)

  import breakface_r8o_checks as BF
  BF.run(put, breaks, det, allow, label)   breaks = [(key, part, p0, n_out, slice_d)], det = the detachable part names (a part's group
                                          is its mesh + its non-part mesh descendants, as Unity detaches it)
Returns the measured numbers per end.
"""
import bpy, math
from mathutils import Vector as V
from mathutils.bvhtree import BVHTree

DARK = ('metal_dark', 'cove', 'well_dark', 'ck_black')
LINER_SKIP = ('paint', 'glass', 'well', 'well_dark')
REACH = 0.50
COVER = 0.60


def group(name, det):
    O = bpy.data.objects
    out = []

    def walk(o):
        if o.type == 'MESH':
            out.append(o)
        for c in o.children:
            if c.name not in det:
                walk(c)
    if name in O:
        walk(O[name])
    return out


def tris(objs):
    vs, fs, ms, on = [], [], [], []
    for o in objs:
        me = o.data
        me.calc_loop_triangles()
        M = o.matrix_world
        b = len(vs)
        vs += [M @ v.co for v in me.vertices]
        mats = [m.name if m else '' for m in me.materials]
        for lt in me.loop_triangles:
            fs.append(tuple(i + b for i in lt.vertices))
            ms.append(mats[lt.material_index] if mats else '')
            on.append(o.name)
    return vs, fs, ms, on


def _basis(n):
    ref = V((0, 0, 1)) if abs(n.z) < 0.9 else V((1, 0, 0))
    u = (ref - n * ref.dot(n)).normalized()
    return u, n.cross(u)


def _slice(vs, fs, ms, q0, n, on=None):
    """the section outline at q0: segments of every 'paint' face cut by the plane. Round 3 (2026-11-27, FD-32 review): each segment
    carries its object's name; _inside() is the UNION of the per-object outlines (even-odd per object). Even-odd over all objects at
    once cancelled overlapping shells: on the FD-32 the spine_fwd paint overlaps the fuselage outline at y -1.90, so the overlap (and the
    spine lobe) counted as 'outside' and the aft end was sampled on 1547 rays instead of ~3300."""
    u, w = _basis(n)
    segs = []
    for k, t in enumerate(fs):
        if ms[k] != 'paint':
            continue
        a, b, c = (vs[i] for i in t)
        da, db, dc = (a - q0).dot(n), (b - q0).dot(n), (c - q0).dot(n)
        pts = []
        for (p, dp), (q, dq) in (((a, da), (b, db)), ((b, db), (c, dc)), ((c, dc), (a, da))):
            if (dp < 0) != (dq < 0):
                x = p + (q - p) * (dp / (dp - dq))
                pts.append(((x - q0).dot(u), (x - q0).dot(w)))
        if len(pts) == 2:
            segs.append((pts[0], pts[1], on[k] if on is not None else ''))
    return segs, u, w


def _inside(segs, x, y):
    cr = {}
    for (ax, ay), (bx, by), tag in segs:
        if (ay > y) != (by > y):
            if ax + (y - ay) * (bx - ax) / (by - ay) > x:
                cr[tag] = cr.get(tag, 0) + 1
    return any(v % 2 == 1 for v in cr.values())


def _segdist(segs, x, y):
    best = 9.0
    for (ax, ay), (bx, by), _t in segs:
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 < 1e-16 else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / L2))
        best = min(best, math.hypot(x - ax - t * dx, y - ay - t * dy))
    return best


def allowed(allow, key, mat, dep, mix, cover=0.0, relief=1.0):
    """an allow entry is (prefix, materials, min depth, why[, opts]); opts (2026-11-27 round 2, review of round 1: a full-section wall
    must not pass only because it is labelled 'cockpit'): max_cover = the wall's share of the axial rays at most this, min_relief = at
    least this share of the rays first hits structure (frames, longerons, stringers) standing in front of the wall."""
    for e in allow:
        pre, mats_, dmin, why = e[:4]
        o = e[4] if len(e) > 4 else {}
        if not (key.startswith(pre) and mat in mats_ and mat != 'structure' and dep >= dmin and sum(mix.get(m, 0) for m in mats_) >= 0.90):
            continue
        if cover > o.get('max_cover', 1.0) or relief < o.get('min_relief', 0.0):
            continue
        return why
    return None


def measure(key, part, p0, n, slice_d, det):
    p0, n = V(p0), V(n).normalized()
    objs = group(part, det)
    vs, fs, ms, on = tris(objs)
    pv = [k for k, m in enumerate(ms) if m == 'paint']
    ptree = BVHTree.FromPolygons(vs, [fs[k] for k in pv]) if pv else None
    cos30 = math.cos(math.radians(30))
    nrm, area, cen = [], [], []
    for t in fs:
        a, b, c = (vs[i] for i in t)
        nn = (b - a).cross(c - a)
        area.append(nn.length / 2); nrm.append(nn.normalized() if nn.length > 1e-14 else V((0, 0, 0))); cen.append((a + b + c) / 3)
    out = dict(part=part, objects=len(objs))
    # ---------------- C1
    A, bym = 0.0, {}
    for k, t in enumerate(fs):
        m = ms[k]
        if m == 'paint' or area[k] < 1e-12 or abs(nrm[k].dot(n)) < cos30:
            continue
        if any(abs((vs[i] - p0).dot(n)) > 0.012 for i in t):
            continue
        if ptree is not None:
            h = ptree.find_nearest(cen[k])
            if h[0] is not None and h[3] <= 0.010:
                continue
        A += area[k]; bym[m] = bym.get(m, 0.0) + area[k]
    out['C1'] = (round(A, 4), {m: round(a, 4) for m, a in bym.items()})
    # ---------------- rays: C10 / C11
    tree = BVHTree.FromPolygons(vs, fs)
    segs, u, w = _slice(vs, fs, ms, p0 - n * slice_d, n, on)
    planes, deep = {}, {}
    tot = 0
    hits = []                      # (depth, material) of every ray's first front-face hit (round 2: relief in front of a deep wall)
    first = {}
    if segs:
        xs_ = [c for s_ in segs for c, _ in s_[:2]]; ys_ = [c for s_ in segs for _, c in s_[:2]]
        step = 0.015
        x = min(xs_)
        while x <= max(xs_):
            y = min(ys_)
            while y <= max(ys_):
                if _inside(segs, x, y) and _segdist(segs, x, y) > 0.012:
                    q = p0 + u * x + w * y
                    pp = q + n * 0.5
                    d = -n
                    tot += 1
                    hit = None
                    for _ in range(60):
                        h = tree.ray_cast(pp, d, 5.0)
                        if h[0] is None:
                            break
                        if h[1].dot(d) < 0:
                            hit = h
                            break
                        pp = h[0] + d * 1e-5
                    if hit is not None:
                        dep = (q - hit[0]).dot(n)
                        m = ms[hit[2]]
                        hits.append((dep, m))
                        first[m] = first.get(m, 0) + 1
                        nh = hit[1].normalized()
                        if m != 'paint' and abs(nh.dot(n)) >= math.cos(math.radians(5)) and dep <= 0.15:
                            kp = round(dep / 0.004)
                            planes[kp] = planes.get(kp, 0) + 1
                        if m != 'paint' and abs(nh.dot(n)) >= math.cos(math.radians(10)) and dep <= REACH:
                            kd = round(dep / 0.006)
                            e = deep.setdefault(kd, [0, {}, 0.0])
                            e[0] += 1; e[1][m] = e[1].get(m, 0) + 1; e[2] += dep
                    else:
                        first['(none)'] = first.get('(none)', 0) + 1
                y += step
            x += step
    pm = 0
    for kp in planes:
        pm = max(pm, planes[kp] + planes.get(kp + 1, 0))
    best = None
    for kd, (c_, mm, ds) in deep.items():
        nb = deep.get(kd + 1)
        c2, mm2, ds2 = c_, dict(mm), ds
        if nb:
            c2 += nb[0]; ds2 += nb[2]
            for m_, v_ in nb[1].items():
                mm2[m_] = mm2.get(m_, 0) + v_
        if best is None or c2 > best[0]:
            best = (c2, mm2, ds2 / max(c2, 1))
    out['rays'] = tot
    out['first'] = {k: round(v / max(tot, 1), 3) for k, v in sorted(first.items(), key=lambda kv: -kv[1])}
    out['C10'] = round(pm / tot, 3) if tot else None
    if best is not None and tot:
        mat_ = max(best[1].items(), key=lambda kv: kv[1])[0]
        out['C11'] = (round(best[0] / tot, 3), round(best[2], 3), mat_, {m_: round(v_ / best[0], 2) for m_, v_ in best[1].items()})
        out['relief'] = round(sum(1 for d_, m_ in hits if m_ in ('structure', 'tank') and d_ < best[2] - 0.01) / tot, 3)
    else:
        out['C11'] = (0.0, 0.0, '', {})
        out['relief'] = 0.0
    # ---------------- C8 seam dark
    tot8, lit = 0, {}
    for k, t in enumerate(fs):
        m = ms[k]
        if m in LINER_SKIP or area[k] < 1e-10 or ptree is None:
            continue
        ds = [(vs[i] - p0).dot(n) for i in t]
        if max(ds) > 0.0005 or min(ds) < -0.0255:
            continue
        hs = ptree.find_nearest(cen[k])
        if hs[0] is None or hs[3] > 0.016 or (cen[k] - hs[0]).dot(hs[1]) > 0:
            continue
        inplane = max(abs(d_) for d_ in ds) < 0.001
        if not inplane and abs(hs[1].normalized().dot(nrm[k])) < 0.7:
            continue
        tot8 += 1
        if m not in DARK:
            lit[m] = lit.get(m, 0) + 1
    out['C8'] = (tot8, lit)
    # ---------------- C6 structure short of the plane (inside the section only)
    viol, near = [], 9.0
    seg0, u0, w0 = _slice(vs, fs, ms, p0 - n * slice_d, n, on)
    for k, t in enumerate(fs):
        if ms[k] not in ('structure', 'tank'):
            continue
        ds = [(p0 - vs[i]).dot(n) for i in t]          # depth inside the part
        dmin = min(ds)
        lim = 0.015 if ms[k] == 'structure' else 0.04
        if dmin >= lim - 1e-4 or dmin < -1.0:
            if dmin < 0.6:
                near = min(near, dmin)
            continue
        c = cen[k]
        if seg0 and not _inside(seg0, (c - p0).dot(u0), (c - p0).dot(w0)):
            continue
        near = min(near, dmin)
        viol.append((on[k], ms[k], round(dmin * 1000, 1)))
    out['C6'] = (round(near * 1000, 1), len(viol), sorted(set(viol))[:6])
    return out


def run(put, breaks, det, allow=(), label='', c1_max=0.03):
    meas = {}
    for key, part, p0, n, sd in breaks:
        meas[key] = measure(key, part, p0, n, sd, det)
    c1bad = {k: v['C1'] for k, v in meas.items() if v['C1'][0] > c1_max}
    put(f'{label}break C1 break_flat (no disc / cap in any break plane): at every break end the non-paint faces in the plane (within 12 mm, '
        f'normal within 30 deg) more than 10 mm inside the skin sum to <= {c1_max} m2', not c1bad,
        f'{len(meas)} ends; over {c1bad}; ' + ', '.join(f'{k} {v["C1"][0]}' for k, v in meas.items()))
    c10bad = [k for k, v in meas.items() if v['C10'] is None or v['C10'] > 0.30]
    put(f'{label}break C10 break_one_plane (no full rib / bulkhead just behind the plane): at every break end <= 30 % of the axial rays (15 mm grid) '
        'have their first hit on one plane across the axis within 0.15 m', not c10bad,
        f'bad {c10bad}; ' + ', '.join(f'{k} {v["C10"]}' for k, v in meas.items()))
    bad11, ok11 = [], []
    for k, v in meas.items():
        cv, dp, mat_, mix = v['C11']
        if cv <= COVER:
            continue
        why = allowed(allow, k, mat_, dp, mix, cv, v.get('relief', 0.0))
        (ok11 if why else bad11).append(f'{k} {cv:.2f} at {dp:.2f} m {mat_}' + (f' [{why}]' if why else ''))
    put(f'{label}break C11 break_deep_wall: no single non-paint plane across the axis is the first hit of > {int(COVER * 100)} % of the axial rays within '
        f'{REACH} m of any break, except the documented walls (cockpit walls, bay-end walls in the liner paint; never structure)', not bad11,
        f'over, not allowed: {bad11}; allowed: {ok11}; max plane per end: ' + ', '.join(f'{k} {v["C11"][0]}@{v["C11"][1]}{v["C11"][2][:3]}' for k, v in meas.items()))
    # C12 (2026-11-27 round 2; round 3 after the review of round 2): at every fuselage end into a cockpit part the largest non-paint plane
    # within 0.5 m covers <= max_cover of the axial view (round 3: 0.50, no 'cockpit wall' exemption: the round 2 dark wall 0.22 m in
    # still covered 0.64 / 0.81 = the divider, darker); the structure in front of it (relief) is reported
    rel = [e for e in allow if len(e) > 4 and 'min_relief' in e[4]]
    rows12, bad12 = [], []
    for k, v in meas.items():
        for e in rel:
            if not k.startswith(e[0]):
                continue
            cv, dp, mat_, mix = v['C11']
            r_ = v.get('relief', 0.0)
            ok_ = cv <= e[4].get('max_cover', 1.0) and (cv <= COVER or r_ >= e[4]['min_relief'])
            (rows12 if ok_ else bad12).append(f'{k} {mat_ or "-"} {cv:.2f} at {dp:.2f} m, structure in front {r_:.2f}')
    if rel:
        o_ = rel[0][4]
        put(f'{label}break C12 cockpit_wall_share (round 3, review of round 2: a dark cockpit wall over 0.64 / 0.81 of the view is still the divider): at every '
            f'fuselage end the largest non-paint plane within {REACH} m (the cockpit wall included) is the first hit of <= {o_.get("max_cover", 1.0):.2f} '
            'of the axial rays; the bays in front of the walls carry their fittings (tank / radio / frames / truss)', bool(rows12 or bad12) and not bad12,
            f'bad {bad12}; ok {rows12}')
    c8bad = {k: v['C8'] for k, v in meas.items() if v['C8'][0] == 0 or v['C8'][1]}
    put(f'{label}break C8 seam_dark (seam backing): at every break end the lining within 25 mm of the plane (liner band, skin edge strips) '
        'is dark (metal_dark / cove) and present', not c8bad,
        f'bad {c8bad}; ' + ', '.join(f'{k} {v["C8"][0]}' for k, v in meas.items()))
    c6bad = {k: v['C6'] for k, v in meas.items() if v['C6'][1]}
    put(f'{label}break C6 stubs_short: no structure face inside the section reaches within 15 mm of a break plane or past it (tank 40 mm)', not c6bad,
        f'bad {c6bad}; nearest per end (mm): ' + ', '.join(f'{k} {v["C6"][0]}' for k, v in meas.items()))
    return meas


# ===================================================================================================== round 3 rows (2026-11-27)
def _scene_tris(skip=lambda o: False):
    vs, fs, ms, on = [], [], [], []
    for o in bpy.data.objects:
        if o.type != 'MESH' or o.hide_render or skip(o):
            continue
        a, b, c, d = tris([o])
        k = len(vs)
        vs += a; fs += [tuple(i + k for i in t) for t in b]; ms += c; on += d
    return vs, fs, ms, on


def eye_bay(put, eye, ya, yb, label='', struct='fus_center_struct', n_dirs=20000, offs=(-0.05, 0.0, 0.05), skip=()):
    """round 3 (regression review of round 2: the wall-station truss tubes stood 10 mm on the PILOT side of the cockpit walls, 304 / 230
    eye-ray hits): rays from the pilot eye (and +-5 cm sideways) over the whole sphere; the first FRONT-face hit (Unity culls back faces;
    glass skipped) must never be a face of `struct` (fus_center_struct, the break-bay structure) with its centre inside the cockpit bay
    (ya + 4 mm < y < yb - 4 mm). Not counted: its ck_lining strips (cockpit-side closures of the walls), the fabric_in lining round
    the cockpit opening and faces within 10 mm of the skin (the inner skin's edge strips at the opening rim; FD-32: 50 hits since 1.9.14)."""
    vs, fs, ms, on = _scene_tris(lambda o: o.name.startswith(tuple(skip)))
    tree = BVHTree.FromPolygons(vs, fs)
    pk = [k for k, m in enumerate(ms) if m == 'paint']
    ptree = BVHTree.FromPolygons(vs, [fs[k] for k in pk])
    hits, tot, rim = {}, 0, 0
    E = V(eye)
    for dx in offs:
        e = E + V((dx, 0, 0))
        for i in range(n_dirs):
            z = 1 - 2 * (i + 0.5) / n_dirs
            r = math.sqrt(max(0.0, 1 - z * z)); ph = i * 2.399963
            d = V((r * math.cos(ph), r * math.sin(ph), z))
            pp = e; tot += 1
            for _ in range(40):
                h = tree.ray_cast(pp, d, 10.0)
                if h[0] is None:
                    break
                if h[1].dot(d) >= 0 or ms[h[2]] == 'glass':
                    pp = h[0] + d * 1e-5
                    continue
                k = h[2]
                if on[k] == struct and ms[k] not in ('ck_lining', 'fabric_in'):
                    cc = sum((vs[j] for j in fs[k]), V()) / 3
                    cy = cc.y
                    hp = ptree.find_nearest(cc)
                    if hp[0] is not None and hp[3] < 0.010:
                        rim += 1                 # inner-skin edge strips at the skin (the cockpit opening rim, 1.9.14), not bay structure
                    elif ya + 0.004 < cy < yb - 0.004:
                        key = (ms[k], round(cy, 2))
                        hits[key] = hits.get(key, 0) + 1
                break
    n = sum(hits.values())
    put(f'{label}break eye_bay (round 3: nothing of the break-bay structure inside the cockpit; round 2 put the wall-station truss 10 mm on the pilot '
        f'side of the walls): from the eye +-5 cm, {len(offs) * n_dirs} rays, no first front-face hit on {struct} (ck_lining strips / opening fabric_in lining aside) between the cockpit '
        f'walls y {ya:+.3f} .. {yb:+.3f} (more than 10 mm inside the skin)', n == 0, dict(hits=n, rays=tot, rim_strip_hits=rim, where=sorted(hits.items(), key=lambda kv: -kv[1])[:8]))
    return n


def poke_sky(put, part, struct, baseline, det, label='', tol=0.0015, n_dirs=400):
    """round 3 (regression review of round 2: the 60 mm wall frame stood 2-3.4 mm out through the gun-trough floor, Mk I 49 vertices with
    a sky view, FD-32 12): vertices of `struct` more than `tol` outside the paint skin of `part`'s group (the part + its non-part
    children, as Unity detaches it: not the lower-wing root fillets, whose paint lies inside the fuselage) that see the sky (>= 1 of
    n_dirs directions free of every other mesh) must not exceed the round 1 / 1.9.14 baseline."""
    O = bpy.data.objects
    grp = group(part, det)
    pv, pf = [], []
    for o in grp:
        a, b, c, d = tris([o])
        k = len(pv)
        pv += a; pf += [tuple(i + k for i in t) for j_, t in enumerate(b) if c[j_] == 'paint']
    ptree = BVHTree.FromPolygons(pv, pf)
    vs, fs, ms, on = _scene_tris(lambda o: o.name == struct)
    atree = BVHTree.FromPolygons(vs, fs)
    dirs = []
    for i in range(n_dirs):
        z = 1 - 2 * (i + 0.5) / n_dirs
        r = math.sqrt(max(0.0, 1 - z * z)); ph = i * 2.399963
        dirs.append(V((r * math.cos(ph), r * math.sin(ph), z)))
    so = O[struct]; M = so.matrix_world
    me = so.data
    mats = [m.name if m else '' for m in me.materials]
    vmat = {}
    for p_ in me.polygons:
        for vi in p_.vertices:
            vmat.setdefault(vi, mats[p_.material_index] if mats else '')
    out, worst = [], 0.0
    for vi, v in enumerate(me.vertices):
        if vmat.get(vi) == 'paint':
            continue
        w = M @ v.co
        h = ptree.find_nearest(w)
        if h[0] is None:
            continue
        dd = (w - h[0]).dot(h[1])
        if dd <= tol:
            continue
        esc = sum(1 for d in dirs if atree.ray_cast(w + d * 0.001, d, 50.0)[0] is None)
        if esc:
            out.append([round(w.x, 3), round(w.y, 3), round(w.z, 3), round(dd * 1000, 1), esc]); worst = max(worst, dd)
    put(f'{label}break poke_sky (round 3: no new struct vertex through the skin; round 2 wall frame poked out of the gun troughs): {struct} vertices more '
        f'than {tol * 1000:.1f} mm outside the {part} paint that see the sky <= {baseline} (round 1 / 1.9.14 baseline)', len(out) <= baseline,
        dict(n=len(out), worst_mm=round(worst * 1000, 1), pts=out[:8]))
    return len(out)
