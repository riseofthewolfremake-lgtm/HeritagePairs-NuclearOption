"""Heritage Pairs 1.8.3 (offline B): internals the stock way (docs/stock_internals_study.md) and the 'specks' fix.

Stock aircraft carry their internals as extra submeshes of the part meshes, drawn with the stock `aircraft_structure` material; the
Unity builders map our `structure` material to it (NimrodBuild / FD32Build StockStructure). Here:
  kestrel(mb)        Mk I: Rolls-Royce Kestrel V12 body inside the cowling (reduction gear, crankcase, two 60-degree cylinder banks with
                     cam covers, supercharger + magnetos at the back), engine bearers to the firewall line, fuselage fuel tank
                     behind the engine under the gun decking (the FuelTank component already sits on fus_engine).
  fd32_power(mb)     FD-32: electric drive motor behind the prop, turbogenerator (intake bell, compressor / turbine core, generator),
                     exhaust collectors to the six side ports, battery packs fore / aft of the sensor bay, turbine fuel tank, cables.
  Both go into the fus_engine_struct child (NOT the fus_engine render / collider mesh): no part mass, CoM, collider or CG changes.
  The firewall disc that closed the fus_engine aft end is no longer built (FIREWALL_ON_ENGINE False): the firewall stays with the
  fuselage (fus_center's tank bulkhead at y -0.065), so a torn-off engine section shows the back of the engine and its bearers.

  tuck(objs, skins, names)   the 'small dark specks' on the Mk I side skin (in-game 1.8.0, ingame_180/edge_nim_zoom.png): cockpit
                     walls / frame tubes / sight base / lining poke through the fuselage skin by up to 9 mm (poke_scan_r183.py). Every
                     vertex of those objects that lies less than INSIDE m under a skin face (perpendicular foot inside the face, i.e.
                     not past the cockpit hole edge) is moved to INSIDE m under it.
"""
import math
from mathutils import Vector as V, Matrix
from b25h_geom import MeshBuf, loft, fan_cap, cylinder, oriented_quad, circle_pts
import nimrod_structure as ST

FIREWALL_ON_ENGINE = False
INSIDE = 0.004                   # under the 2.5 mm inner skin (2.5 mm put the Aldis base on the cockpit inner skin: z-fight row)


# ------------------------------------------------------------------------------------------- primitives
def _frame(axis, up):
    w = V(axis).normalized()
    u = V(up).cross(w).normalized()          # right
    v = w.cross(u).normalized()              # up
    return u, v, w


def sring(c, u, v, hw, hh, n=4.0, N=24, hb=None):
    """superellipse ring around c in the (u, v) plane: half width hw, half height hh (below: hb)."""
    hb = hh if hb is None else hb
    pts = []
    for j in range(N):
        a = 2 * math.pi * j / N
        s, co = math.sin(a), math.cos(a)
        x = hw * math.copysign(abs(s) ** (2.0 / n), s)
        h = hh if co >= 0 else hb
        z = h * math.copysign(abs(co) ** (2.0 / n), co)
        pts.append(V(c) + u * x + v * z)
    return pts


def body(mb, p0, p1, up, prof, n=4.0, N=16, mat='structure', caps=True):
    """lofted body from p0 to p1 (axis), sections prof = [(t, hw, hh[, hb]), ...] (t 0..1 along the axis); closed ends."""
    p0, p1 = V(p0), V(p1)
    u, v, w = _frame(p1 - p0, up)
    rings = []
    for row in prof:
        t, hw, hh = row[0], row[1], row[2]
        hb = row[3] if len(row) > 3 else hh
        rings.append(sring(p0 + (p1 - p0) * t, u, v, hw, hh, n, N, hb))
    loft(mb, rings, mat, smooth=True)
    if caps:
        fan_cap(mb, rings[0], sum(rings[0], V()) / N, mat, -(p1 - p0))
        fan_cap(mb, rings[-1], sum(rings[-1], V()) / N, mat, (p1 - p0))
    return rings


def bar(mb, a, b, r, mat='structure', N=6):
    cylinder(mb, V(a), V(b), r, N=N, mat=mat, cap0=True, cap1=True, smooth=True)


def rbox(mb, c, size, mat='structure', n=6.0, N=12):
    """rounded box (superellipse section n along y), centre c, size (x, y, z)."""
    c = V(c); sx, sy, sz = size
    body(mb, c - V((0, sy / 2, 0)), c + V((0, sy / 2, 0)), V((0, 0, 1)),
         [(0.0, sx / 2 * 0.96, sz / 2 * 0.96), (0.02, sx / 2, sz / 2), (0.98, sx / 2, sz / 2), (1.0, sx / 2 * 0.96, sz / 2 * 0.96)],
         n=n, N=N, mat=mat)


# ------------------------------------------------------------------------------------------- Mk I: Kestrel V12
KESTREL = dict(y_rear=0.14, y_front=2.15, crank_z=-0.17, bank_deg=30.0)


def kestrel(mb):
    """Rolls-Royce Kestrel (upright 60-degree V12, ~1.85 m long with the reduction gear, ~0.75 m wide, ~0.95 m tall) in the Mk I
    cowling. Fits: cowl inner skin (2.5 mm inside the skin), Vickers bodies in the troughs (x +-0.165, z > 0.39), exhaust manifolds
    outside the skin, radiator / oil cooler outside the belly. Numbers in metres, Blender frame."""
    up = V((0, 0, 1))
    # crankcase: y 0.42 .. 1.96, hull of a rounded box, bottom sump deeper at the back
    body(mb, (0, 0.42, -0.17), (0, 1.96, -0.17), up, [(0.0, 0.15, 0.10, 0.16), (0.04, 0.17, 0.12, 0.20), (0.5, 0.18, 0.12, 0.22),
                                                        (0.96, 0.17, 0.12, 0.17), (1.0, 0.15, 0.10, 0.14)], n=4.0, N=20)
    # cylinder banks: 6 cylinders each, block inclined 30 deg out, cam cover on top
    for s in (-1, 1):
        a = math.radians(KESTREL['bank_deg']) * s
        d = V((math.sin(a), 0, math.cos(a)))           # bank axis (up and out)
        base = V((s * 0.05, 0, -0.10))
        c0 = base + d * 0.16                           # block centre line
        body(mb, (c0.x, 0.50, c0.z), (c0.x, 1.86, c0.z), d, [(0.0, 0.075, 0.13), (0.015, 0.085, 0.14), (0.985, 0.085, 0.14), (1.0, 0.075, 0.13)], n=6.0, N=12)
        cc = base + d * 0.33                           # cam cover (rounded, narrower)
        body(mb, (cc.x, 0.52, cc.z), (cc.x, 1.84, cc.z), d, [(0.0, 0.040, 0.020), (0.02, 0.055, 0.035), (0.98, 0.055, 0.035), (1.0, 0.040, 0.020)], n=3.0, N=10)
    # reduction gear housing at the front (prop shaft above the crank line) and the shaft into the spinner back plate
    body(mb, (0, 1.92, -0.06), (0, 2.16, -0.03), up, [(0.0, 0.17, 0.22, 0.20), (0.5, 0.18, 0.23, 0.20), (1.0, 0.13, 0.16, 0.12)], n=2.4, N=16)
    cylinder(mb, V((0, 2.14, 0.0)), V((0, 2.30, 0.0)), 0.055, N=10, mat='structure')
    # supercharger + accessory case at the back, magnetos
    body(mb, (0, 0.14, -0.12), (0, 0.44, -0.14), up, [(0.0, 0.15, 0.15), (0.15, 0.19, 0.19), (0.75, 0.19, 0.19), (1.0, 0.16, 0.16)], n=2.2, N=16)
    for s in (-1, 1):
        cylinder(mb, V((s * 0.11, 0.28, 0.06)), V((s * 0.11, 0.44, 0.06)), 0.045, N=8, mat='structure')
    # carburettor + induction pipe under the crankcase
    rbox(mb, (0, 0.35, -0.40), (0.20, 0.18, 0.16))
    body(mb, (0, 0.40, -0.40), (0, 1.20, -0.36), up, [(0.0, 0.05, 0.05), (1.0, 0.05, 0.05)], n=2.0, N=8)
    # engine bearers: two tubular A-frames per side from the firewall corners (y 0.035: 2026-11-22, ends 20+ mm short of the y 0 break) to the crankcase feet
    for s in (-1, 1):
        for zf, zc in ((0.30, -0.06), (-0.40, -0.26)):
            bar(mb, (s * 0.34, 0.035, zf), (s * 0.21, 0.70, zc), 0.016)
            bar(mb, (s * 0.34, 0.035, zf), (s * 0.21, 1.30, zc), 0.016)
        bar(mb, (s * 0.21, 0.70, -0.06), (s * 0.21, 1.30, -0.26), 0.012)
    # fuel tank behind the engine, under the gun decking, between the Vickers bodies (FuelTank on fus_engine)
    fuel_tank(mb)
    front_bulkhead(mb)


def front_bulkhead(mb, y=2.34):
    """the cowl's front closure behind the spinner seen from the open aft end of a torn-off engine section (the cowl front cap faces
    forward only: without the firewall it read as a hole from behind - see-through row)."""
    import nimrod_parts as NP
    r, c = NP.fus_inset_ring(y, 0.004)
    fan_cap(mb, r, c, 'structure', V((0, -1, 0)))


TANK_MAT = 'tank'


def fuel_tank(mb, y0=0.05, y1=0.13, x=0.30, z0=0.12, z1=0.37):
    """saddle tank behind the engine (stock: tanks are FuelTank components; the mesh is only what a torn-off section shows)."""
    # 2026-11-22 (r8o C5 lesson: a light 'structure' box 50 mm behind the fus_engine break read as the "box"): plain tank metal
    # ('tank', Unity <prefix>_tank: lit 0.55 grey), dark straps
    rbox(mb, (0, (y0 + y1) / 2 + 0.06, (z0 + z1) / 2), (2 * x, (y1 - y0) + 0.12, z1 - z0), n=5.0, mat=TANK_MAT)
    for s in (-1, 1):                                  # straps
        for yy in (y0 + 0.04, y1 + 0.08):
            p0, p1 = V((s * (x + 0.006), yy, z0 + 0.02)), V((s * (x + 0.006), yy, z1 - 0.02))
            bar(mb, p0, p1, 0.008, N=4, mat='metal_dark' if TANK_MAT == 'tank' else 'structure')


# ------------------------------------------------------------------------------------------- FD-32: turbo-electric power plant
def fd32_power(mb, bay_y=0.46, bay_r=0.205, bay_cap_z=-0.18):
    """drive motor + turbogenerator + batteries + fuel in the Mk I cowling shape (fd32_spec MASSES note: battery packs + motor +
    turbogenerator in fus_engine). Clear of the sensor-ball bay liner (radius bay_r around (0, bay_y), below bay_cap_z)."""
    up = V((0, 0, 1))
    # drive motor: finned can behind the prop, shaft into the spinner back plate
    body(mb, (0, 1.62, -0.02), (0, 2.12, -0.01), up, [(0.0, 0.20, 0.20), (0.05, 0.23, 0.23), (0.95, 0.23, 0.23), (1.0, 0.18, 0.18)], n=2.0, N=16)
    for k in range(3):
        y = 1.70 + k * 0.14
        body(mb, (0, y, -0.02), (0, y + 0.018, -0.02), up, [(0.0, 0.245, 0.245), (1.0, 0.245, 0.245)], n=2.0, N=16)
    cylinder(mb, V((0, 2.10, 0.0)), V((0, 2.30, 0.0)), 0.06, N=14, mat='structure')
    # turbogenerator: generator (front), core (compressor / combustor / turbine), intake bell at the back, on the thrust line
    body(mb, (0, 1.22, 0.05), (0, 1.58, 0.03), up, [(0.0, 0.17, 0.17), (0.1, 0.20, 0.20), (0.9, 0.20, 0.20), (1.0, 0.16, 0.16)], n=2.0, N=16)
    body(mb, (0, 0.62, 0.08), (0, 1.22, 0.05), up, [(0.0, 0.19, 0.19), (0.15, 0.15, 0.15), (0.35, 0.17, 0.17), (0.6, 0.15, 0.15),
                                                   (0.8, 0.13, 0.13), (1.0, 0.15, 0.15)], n=2.0, N=16)
    body(mb, (0, 0.50, 0.08), (0, 0.62, 0.08), up, [(0.0, 0.23, 0.23), (1.0, 0.19, 0.19)], n=2.0, N=16)
    # exhaust: from the turbine section out to the side collectors that feed the six flush ports per side (z 0.06)
    for s in (-1, 1):
        bar(mb, (s * 0.12, 0.80, 0.08), (s * 0.33, 0.95, 0.06), 0.05, N=10)
        body(mb, (s * 0.355, 0.42, 0.06), (s * 0.355, 1.72, 0.06), up, [(0.0, 0.03, 0.05), (0.05, 0.045, 0.06), (0.95, 0.045, 0.06), (1.0, 0.03, 0.05)], n=3.0, N=16)
    # battery packs: forward pair beside / under the motor, aft pair behind the bay; boxes with module ribs
    for s in (-1, 1):
        rbox(mb, (s * 0.18, 1.20, -0.37), (0.24, 0.66, 0.20))
    rbox(mb, (0, 0.11, -0.36), (0.56, 0.16, 0.26))           # aft of the bay (bay front edge y 0.255)
    for s in (-1, 1):                                         # its mounting lugs to the frame tubes
        bar(mb, (s * 0.26, 0.11, -0.37), (s * 0.335, 0.11, -0.385), 0.012)
    # turbine fuel tank behind the turbogenerator under the gun decking (FuelTank on fus_engine)
    fuel_tank(mb, y1=0.20)
    front_bulkhead(mb)
    # power cables motor <- generator, batteries -> bus
    for s in (-1, 1):
        bar(mb, (s * 0.12, 1.55, -0.10), (s * 0.12, 1.66, -0.12), 0.018, N=8)
        bar(mb, (s * 0.20, 0.88, -0.30), (s * 0.12, 0.70, -0.12), 0.015, N=8)
    # mounts: tube frame from the firewall line to the motor / generator
    for s in (-1, 1):
        for zf, zc in ((0.30, 0.10), (-0.40, -0.14)):
            bar(mb, (s * 0.34, 0.035, zf), (s * 0.17, 1.30, zc), 0.016)
        bar(mb, (s * 0.17, 1.30, 0.10), (s * 0.17, 1.30, -0.14), 0.012)


def check_bay_clear(mb, bay_y=0.46, bay_r=0.205, bay_cap_z=-0.18, margin=0.01):
    bad = [p for p in mb.verts if p.z < bay_cap_z + margin and math.hypot(p.x, p.y - bay_y) < bay_r + margin]
    return bad


def inside_skin(mb, y_lo, y_hi, margin=0.008):
    """vertices of mb (y in y_lo..y_hi) closer than margin to the fuselage skin section (or outside it): list."""
    bad = []
    for p in mb.verts:
        if not (y_lo <= p.y <= y_hi):
            continue
        hw, zt, zb, n = ST.fus_params(p.y)
        if p.z > zt - margin or p.z < zb + margin:
            bad.append(p); continue
        if abs(p.x) > ST.fus_half_width(p.y, p.z) - margin:
            bad.append(p)
    return bad


# ------------------------------------------------------------------------------------------- tuck inner parts under the skin
def _trees(objs, skins):
    import bmesh
    from mathutils.bvhtree import BVHTree
    trees = []
    for sn in skins:
        so = objs.get(sn)
        if so is None:
            continue
        bm = bmesh.new(); bm.from_mesh(so.data); bm.transform(so.matrix_world); bm.normal_update()
        mats = [m.name if m else '' for m in so.data.materials]
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if mats[f.material_index] != 'paint'], context='FACES')
        trees.append(BVHTree.FromBMesh(bm)); bm.free()
    return trees


def _need(trees, p, inside, reach):
    """displacement that puts world point p `inside` under the nearest skin face (perpendicular foot inside it), or None."""
    best = None
    for t in trees:
        loc, nrm, idx, d = t.find_nearest(p, reach)
        if loc is not None and (best is None or d < best[3]):
            best = (loc, nrm, idx, d)
    if best is None:
        return None
    loc, nrm, idx, d = best
    off = p - loc
    sd = off.dot(nrm)
    if sd > -inside and (off - nrm * sd).length < 1e-4:
        return -nrm * (sd + inside)
    return None


def tuck(objs, skins=('fus_center', 'fus_engine', 'fus_rear'), select=lambda n: n.startswith('cockpit_') and n != 'cockpit_coaming',
         inside=INSIDE, reach=0.012):
    """move every vertex of the selected objects that is less than `inside` under a skin face (perpendicular foot inside the face) to
    `inside` under it. A mesh island in which that per-vertex move would flip a face (thin plates / brackets) is instead moved rigidly by
    its largest required displacement (repeated up to 4 times). Returns {object: moved vertices}."""
    trees = _trees(objs, skins)
    out = {}
    for name, o in objs.items():
        if o.type != 'MESH' or not select(name):
            continue
        me = o.data
        M = o.matrix_world; Mi = M.inverted(); R = M.to_3x3()
        W = [M @ v.co for v in me.vertices]
        # islands (vertex connectivity through faces)
        par = list(range(len(W)))
        def f_(a):
            while par[a] != a:
                par[a] = par[par[a]]; a = par[a]
            return a
        for pl in me.polygons:
            vs = list(pl.vertices)
            for a in vs[1:]:
                ra, rb = f_(vs[0]), f_(a)
                if ra != rb:
                    par[ra] = rb
        hit = {}
        for i, p in enumerate(W):
            d = _need(trees, p, inside, reach)
            if d is not None:
                hit.setdefault(f_(i), []).append((i, d))
        if not hit:
            continue
        # each poking island gets its own depth (rank by how far it poked: the outermost sheet stays shallowest, ribs / tubes on it go
        # 0.8 mm deeper each) so two islands are never flattened onto the same surface (z-fight row)
        order = sorted(hit, key=lambda k: -max(d.length for i, d in hit[k]))
        new = list(W)
        for rk, isl in enumerate(order):
            extra = 0.0008 * rk
            for i, d in hit[isl]:
                new[i] = W[i] + d + d.normalized() * extra
        flipped = set()
        for pl in me.polygons:
            vs = list(pl.vertices)
            if f_(vs[0]) not in hit:
                continue
            a0 = (W[vs[1]] - W[vs[0]]).cross(W[vs[-1]] - W[vs[0]])
            a1 = (new[vs[1]] - new[vs[0]]).cross(new[vs[-1]] - new[vs[0]])
            if a0.length > 1e-12 and (a1.length < 1e-12 or a0.normalized().dot(a1.normalized()) < 0.5):
                flipped.add(f_(vs[0]))
        if flipped:
            adj = [[] for _ in W]
            for e in me.edges:
                a_, b_ = e.vertices
                adj[a_].append(b_); adj[b_].append(a_)
        for isl in flipped:
            idx = [i for i in range(len(W)) if f_(i) == isl]
            for i in idx:
                new[i] = W[i]
            if len(idx) <= 200:                     # small brackets / plates: rigid moves by the largest need (<= 3 x, <= 25 mm)
                tot = V()
                for _ in range(3):
                    ds = [d for d in (_need(trees, new[i], inside, reach) for i in idx) if d is not None]
                    if not ds:
                        break
                    D = max(ds, key=lambda v: v.length) * 1.05
                    if (tot + D).length > 0.025:
                        break
                    tot += D
                    for i in idx:
                        new[i] = new[i] + D
            else:                                   # big sheets (the lining): the displacement spread over 4 rings of neighbours
                disp = {}
                for i, d in hit[isl]:
                    disp[i] = d
                front = dict(disp)
                for _ in range(4):
                    nxt = {}
                    for i, d in front.items():
                        for j in adj[i]:
                            dj = d * 0.6
                            if j not in disp or dj.length > disp[j].length:
                                if j not in disp or disp[j].length < dj.length:
                                    nxt[j] = dj
                    for j, d in nxt.items():
                        disp[j] = d
                    front = nxt
                for i, d in disp.items():
                    new[i] = W[i] + d
        n = 0
        for i, p in enumerate(new):
            if (p - W[i]).length > 1e-7:
                me.vertices[i].co = Mi @ p; n += 1
        if n:
            me.update(); out[name] = n
    return out


def poke_count(objs, skins=('fus_center', 'fus_engine', 'fus_rear'), select=lambda n: n.startswith('cockpit_') and n != 'cockpit_coaming',
               margin=0.001, reach=0.012):
    """the check: vertices of the selected objects less than `margin` under a skin face (perpendicular foot inside the face)."""
    import bmesh
    from mathutils.bvhtree import BVHTree
    trees = []
    for sn in skins:
        so = objs.get(sn)
        if so is None:
            continue
        bm = bmesh.new(); bm.from_mesh(so.data); bm.transform(so.matrix_world); bm.normal_update()
        mats = [m.name if m else '' for m in so.data.materials]
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if mats[f.material_index] != 'paint'], context='FACES')
        trees.append(BVHTree.FromBMesh(bm)); bm.free()
    out = {}
    for name, o in objs.items():
        if o.type != 'MESH' or not select(name):
            continue
        M = o.matrix_world
        hits = []
        for v in o.data.vertices:
            p = M @ v.co
            for t in trees:
                loc, nrm, idx, d = t.find_nearest(p, reach)
                if loc is None:
                    continue
                off = p - loc; sd = off.dot(nrm)
                if sd > -margin and (off - nrm * sd).length < 1e-4:
                    hits.append((round(p.x, 3), round(p.y, 3), round(p.z, 3), round(sd * 1000, 2)))
                    break
        if hits:
            out[name] = hits
    return out
