"""Place the B-17G fal 3D props (assets/model_b17g/src/fal/opt/*.glb; fal manifests in src/fal/*/fal_manifest.jsonl) on the model.

Orientation of every generated mesh is decided from its own geometry (logged), then scaled to the real part size:
- prop3: blade disc normal = the axis with the smallest extent; the spinner end is the end with the smaller radius. The fal model
  carries a cowl drum behind the blades: everything behind the blade plane + 0.06 R is cut off and the hub closed with a disc.
- r1820: axis = smallest extent; front = end with the gear case (smaller radius near the end).
- mainwheel: axle = smallest extent; the generated tyre is flattened at its top, so the lower half is mirrored over the axle.
- tailwheel (wheel + fork + strut): wheel = the lowest round island region; trails aft of the pivot.
- turrets: axis / front from extents; ball window +X of the generated mesh.
Every mesh goes through the face-orientation check in check_b17g_model.py (rays from outside meet front faces).
"""
import bpy, bmesh, os, math
from mathutils import Vector as V, Matrix, Quaternion
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OPT = os.path.abspath(os.path.join(HERE, '..', '..', 'assets', 'model_b17g', 'src', 'fal', 'opt'))
LOG = []


def log(*a):
    s = ' '.join(str(x) for x in a); LOG.append(s); print('[props]', s)


def load(name):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(OPT, name + '.glb'))
    new = [o for o in bpy.data.objects if o not in before]
    ms = [o for o in new if o.type == 'MESH']
    me = ms[0].data.copy()
    me.transform(ms[0].matrix_world)
    for o in new:
        bpy.data.objects.remove(o)
    return me


def verts(me):
    a = np.zeros(len(me.vertices) * 3, np.float32); me.vertices.foreach_get('co', a)
    return a.reshape(-1, 3)


def bbox(P):
    return P.min(0), P.max(0)


def rot_to(src_axis, dst_axis, src_up, dst_up):
    """rotation mapping src_axis->dst_axis and src_up->dst_up (orthonormalised)."""
    def basis(a, u):
        a = V(a).normalized(); u = (V(u) - a * V(u).dot(a)).normalized(); w = a.cross(u)
        return Matrix((a, u, w)).transposed()
    return basis(dst_axis, dst_up) @ basis(src_axis, src_up).inverted()


def apply(me, M3, scale, offset):
    me.transform(Matrix.Translation(offset) @ (M3.to_4x4() * 1.0) @ Matrix.Diagonal((scale, scale, scale, 1)))


def end_radius(P, ax, frac=0.15):
    """radial extent near both ends along axis index ax -> (r_at_min_end, r_at_max_end)."""
    lo, hi = P[:, ax].min(), P[:, ax].max(); L = hi - lo
    c = P.mean(0); oth = [i for i in range(3) if i != ax]
    r = np.sqrt(((P[:, oth] - c[oth]) ** 2).sum(1))
    a = r[P[:, ax] < lo + frac * L]; b = r[P[:, ax] > hi - frac * L]
    return (np.percentile(a, 95) if len(a) else 0), (np.percentile(b, 95) if len(b) else 0)


def cut_keep(me, keep):
    bm = bmesh.new(); bm.from_mesh(me)
    kill = [v for v in bm.verts if not keep(v.co)]
    bmesh.ops.delete(bm, geom=kill, context='VERTS')
    edges = [e for e in bm.edges if len(e.link_faces) == 1]
    if edges:
        bmesh.ops.holes_fill(bm, edges=edges, sides=0)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bm.to_mesh(me); bm.free()


def two_sided(me, off):
    """normals recomputed on the (closed) shell + a reversed twin `off` inside every face: one side always faces the eye."""
    bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in list(bm.faces):
        vs = [bm.verts.new(l.vert.co - f.normal * off) for l in reversed(list(f.loops))]
        try:
            bm.faces.new(vs)
        except ValueError:
            pass
    bm.to_mesh(me); bm.free()


def two_sided_safe(me, off):
    """two_sided, but a face gets no reversed twin when the mesh already has a surface within 1.6 x `off` behind it (a thin fin's
    other face: the twin would lie on it, same facing = z-fight)."""
    from mathutils.bvhtree import BVHTree
    bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    tree = BVHTree.FromBMesh(bm)
    add = []
    for f in list(bm.faces):
        c = f.calc_center_median()
        h = tree.ray_cast(c - f.normal * (off * 0.05), -f.normal, off * 1.6)
        if h[0] is not None:
            continue
        add.append([l.vert.co - f.normal * off for l in reversed(list(f.loops))])
    for pts in add:
        try:
            bm.faces.new([bm.verts.new(p) for p in pts])
        except ValueError:
            pass
    bm.to_mesh(me); bm.free()


def mirror_lower_half(me, ax_up=2, centre=0.0):
    """keep the faces below `centre` along ax_up (straddling vertices clamped onto the plane) and mirror them upward: the generated
    tyre is clipped at its top; both halves meet exactly on the plane and are welded (no seam slit)."""
    bm = bmesh.new(); bm.from_mesh(me)
    kill = [f for f in bm.faces if sum(v.co[ax_up] for v in f.verts) / len(f.verts) > centre]
    bmesh.ops.delete(bm, geom=kill, context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    for v in bm.verts:
        if v.co[ax_up] > centre or v.is_boundary:      # the cut edge lies exactly on the mirror plane (no slit after the weld)
            co = v.co.copy(); co[ax_up] = centre; v.co = co
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    dup = bmesh.ops.duplicate(bm, geom=geom)
    for g in dup['geom']:
        if isinstance(g, bmesh.types.BMVert):
            co = g.co.copy(); co[ax_up] = 2 * centre - co[ax_up]; g.co = co
    bmesh.ops.reverse_faces(bm, faces=[g for g in dup['geom'] if isinstance(g, bmesh.types.BMFace)])
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)     # the welded tyre is one closed shell: consistent outward winding
    bm.to_mesh(me); bm.free()


def clean_slivers(me):
    """round 3 (user: rogue polygons): dissolve zero-area slivers left by the decimation (FBX scan: tail mantlet 12, top turret 4)."""
    import bmesh as _bm
    bm = _bm.new(); bm.from_mesh(me)
    n0 = len(bm.faces)
    _bm.ops.dissolve_degenerate(bm, dist=1e-4, edges=bm.edges[:])
    bad = [f for f in bm.faces if f.calc_area() < 1e-9]
    if bad:
        _bm.ops.delete(bm, geom=bad, context='FACES_ONLY')
    bm.to_mesh(me); me.update(); n1 = len(bm.faces); bm.free()
    return n0 - n1


def obj(name, me, parent, coll, mat_name=None):
    me.name = name
    dropped = clean_slivers(me)
    if dropped:
        log(f'{name}: {dropped} zero-area sliver faces dissolved')
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    if parent is not None:
        me.transform(parent.matrix_world.inverted())     # mesh in the parent's local frame (spins / turns with it)
        o.parent = parent
        o.matrix_parent_inverse = Matrix.Identity(4)
        o.matrix_world = parent.matrix_world.copy()
    if mat_name:
        o['b17g_prop_mat'] = mat_name
    o['b25_info'] = '{"kind": "fal_prop"}'
    return o


def axis_of_min_extent(P):
    lo, hi = bbox(P); return int(np.argmin(hi - lo))


def place_prop(objs, coll, S):
    base = load('prop3')
    P = verts(base); lo, hi = bbox(P); c = (lo + hi) / 2
    ax = axis_of_min_extent(P)
    r0, r1 = end_radius(P, ax, 0.25)
    # the drum end has the larger radius: the spinner (front) is the other end
    front_sign = -1 if r0 < r1 else 1
    # blade plane: where the radial extent peaks
    oth = [i for i in range(3) if i != ax]
    rr = np.sqrt(((P[:, oth] - c[oth]) ** 2).sum(1))
    tips = P[rr > np.percentile(rr, 99)]
    plane = float(tips[:, ax].mean())
    R_mesh = float(np.percentile(rr, 99.9))
    log(f'prop3: axis {"xyz"[ax]}, front {"-+"[front_sign > 0]}, blade plane {plane:.3f}, radius {R_mesh:.3f}, end radii {r0:.3f}/{r1:.3f}')
    keep_lim = plane - front_sign * 0.06 * R_mesh
    cut_keep(base, lambda co: (co[ax] - keep_lim) * front_sign >= 0)
    bm = bmesh.new(); bm.from_mesh(base); bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in list(bm.faces):
        vs = [bm.verts.new(l.vert.co - f.normal * 0.0008 * 0.661 / 1.765) for l in reversed(list(f.loops))]
        try:
            bm.faces.new(vs)
        except ValueError:
            pass
    bm.to_mesh(base); bm.free()
    for o in [x for x in objs.values() if x.name.startswith('prop_') and x.type == 'EMPTY']:
        me = base.copy()
        src_ax = [0, 0, 0]; src_ax[ax] = front_sign
        src_up = [0, 0, 0]; src_up[oth[0]] = 1
        M3 = rot_to(src_ax, (0, 1, 0), src_up, (0, 0, 1))
        sc = S.PROP_R / R_mesh
        off = V(c); off[ax] = plane
        me.transform(Matrix.Translation(-off))
        apply(me, M3, sc, o.matrix_world.translation)
        hub_name = o.name.replace('prop_', 'prop_hub_')
        split_blades(me, o, coll, hub_name, V(o.matrix_world.translation), S.PROP_R)
    return R_mesh


def place_engines(objs, coll, S):
    base = load('r1820')
    P = verts(base); lo, hi = bbox(P); c = (lo + hi) / 2
    ax = axis_of_min_extent(P)
    r0, r1 = end_radius(P, ax, 0.2)
    front_sign = 1 if r1 < r0 else -1          # the gear case end is the narrower end
    oth = [i for i in range(3) if i != ax]
    D = float(max(hi[oth] - lo[oth]))
    log(f'r1820: axis {"xyz"[ax]}, front {"-+"[front_sign > 0]}, diameter {D:.3f}')
    sc0 = (0.80 * 0.78 * 2 - 0.06) / D
    fr0 = hi[ax] if front_sign > 0 else lo[ax]
    cut_keep(base, lambda co: (fr0 - co[ax]) * front_sign <= 0.50 / sc0)     # cylinders + nose case only (the generated rear mount would cross the gear well)
    two_sided_safe(base, 0.0008 / sc0)      # round 5: no twin where a thin fin's other face already lies within 1.6 x the offset (z-fight)
    for o in [x for x in objs.values() if x.name.startswith('engine_') and not x.name.endswith('_hullsrc') and x.type == 'MESH']:
        R = o.get('cowl_r', 0.78)
        me = base.copy()
        src_ax = [0, 0, 0]; src_ax[ax] = front_sign
        src_up = [0, 0, 0]; src_up[oth[0]] = 1
        M3 = rot_to(src_ax, (0, 1, 0), src_up, (0, 0, 1))
        sc = (0.80 * 0.78 * 2 - 0.01) / D
        front = V(c); front[ax] = hi[ax] if front_sign > 0 else lo[ax]
        me.transform(Matrix.Translation(-front))
        apply(me, M3, sc, o.matrix_world.translation + V((0, -0.02, 0)))
        obj(o.name.replace('engine_', 'engine_face_'), me, o, coll, 'pr_r1820')


def place_wheels(objs, coll, S):
    base = load('mainwheel')
    P = verts(base); lo, hi = bbox(P)
    ax = axis_of_min_extent(P)
    oth = [i for i in range(3) if i != ax]
    # true centre from the two full extents (the clipped one is the up axis)
    ext = hi - lo
    up = oth[int(np.argmin([ext[i] for i in oth]))]; along = [i for i in oth if i != up][0]
    cen = (lo + hi) / 2; cen[up] = cen[along] * 0 + (lo[up] + ext[along] / 2)
    log(f'mainwheel: axle {"xyz"[ax]}, clipped axis {"xyz"[up]} ({ext[up]:.3f} vs {ext[along]:.3f}) -> mirrored lower half at {cen[up]:.3f}')
    mirror_lower_half(base, up, float(cen[up]))
    P = verts(base); lo, hi = bbox(P); cen = (lo + hi) / 2
    D = float(hi[along] - lo[along])
    two_sided(base, 0.0008 * D / (2 * S.WHEEL_R))       # see-through 0: a reversed twin behind every tyre face
    for o in []:     # main tyres are procedural round lathes now (b17g_parts.main_gear); the fal tyre is kept only as reference
        me = base.copy()
        src_ax = [0, 0, 0]; src_ax[ax] = 1
        src_up = [0, 0, 0]; src_up[up] = 1
        M3 = rot_to(src_ax, (1, 0, 0), src_up, (0, 0, 1))
        me.transform(Matrix.Translation(-V(cen)))
        sq = [1.0, 1.0, 1.0]; sq[ax] = S.WHEEL_W / (float(hi[ax] - lo[ax]) * 2 * S.WHEEL_R / D)     # tyre width to the real 0.50 m
        me.transform(Matrix.Diagonal((sq[0], sq[1], sq[2], 1.0)))
        apply(me, M3, 2 * S.WHEEL_R / D, o.matrix_world.translation)
        obj(o.name.replace('wheel_main_', 'tyre_main_'), me, o, coll, 'tyre')
    # tail wheel assembly (wheel + fork + short strut)
    base = load('tailwheel')
    P = verts(base); lo, hi = bbox(P)
    ax = axis_of_min_extent(P)
    oth = [i for i in range(3) if i != ax]
    upax = oth[int(np.argmax([hi[i] - lo[i] for i in oth]))]
    along = [i for i in oth if i != upax][0]
    low = P[P[:, upax] < lo[upax] + 0.45 * (hi[upax] - lo[upax])]
    wl, wh = low.min(0), low.max(0)
    wc = (wl + wh) / 2; wc[upax] = lo[upax] + (wh[along] - wl[along]) / 2
    wr = float(wh[along] - wl[along]) / 2
    trail = 1 if wc[along] > (lo[along] + hi[along]) / 2 else -1     # wheel side of the fork along `along`
    log(f'tailwheel: axle {"xyz"[ax]}, up {"xyz"[upax]}, wheel radius {wr:.3f}, wheel trails toward {"-+"[trail > 0]}{"xyz"[along]}')
    o = None      # round 3: the tail tyre + fork are procedural (b17g_parts.tyre_mesh / tail_fork); the fal tail wheel was ONE mesh
    # (wheel + fork) under wheel_tail, so LandingGear spun the whole assembly about the axle (LandingGear.cs 556-558)
    if o is not None:
        lim = float(wc[upax] + 1.45 * wr)
        cut_keep(base, lambda co: co[upax] <= lim)
        me = base.copy()
        src_ax = [0, 0, 0]; src_ax[ax] = 1
        src_up = [0, 0, 0]; src_up[upax] = 1
        src_al = [0, 0, 0]; src_al[along] = trail
        M3 = rot_to(src_al, (0, -1, 0), src_up, (0, 0, 1))      # the wheel trails AFT (-Y)
        me.transform(Matrix.Translation(-V(wc)))
        apply(me, M3, S.TAIL_WHEEL_R / wr, o.matrix_world.translation)
        obj('tyre_tail', me, o, coll, 'pr_tailwheel')


def place_turrets(objs, coll, S):
    spec = {   # fal mesh: (target object, real size (m), how)
        'topturret_ng': ('top_az', 1.00, 'dome'),
        'ballturret_ng': ('ball_el', 1.14, 'ball'),
        'chinturret_ng': ('chin_az', 0.94, 'pod'),
        'tailmantlet': ('tail_el', 0.62, 'mantlet'),
    }
    for nm, (tgt, size, how) in spec.items():
        o = objs.get(tgt)
        if o is None:
            continue
        me = load(nm)
        P = verts(me); lo, hi = bbox(P); c = (lo + hi) / 2; ext = hi - lo
        ax = int(np.argmin(ext))
        if how == 'dome':
            r0, r1 = end_radius(P, ax, 0.12)
            top_sign = 1 if r1 < r0 else -1
            src_up = [0, 0, 0]; src_up[ax] = top_sign
            fwd = [i for i in range(3) if i != ax][0]
            src_f = [0, 0, 0]; src_f[fwd] = 1
            M3 = rot_to(src_up, (0, 0, 1), src_f, (0, 1, 0))
            base_pt = V(c); base_pt[ax] = lo[ax] if top_sign > 0 else hi[ax]
            b0, ext_ax = float(base_pt[ax]), float(ext[ax])
            cut_keep(me, lambda co: (co[ax] - b0) * top_sign <= 0.24 * ext_ax)     # keep the ring base only (the glass dome + thin frame are ours)
            two_sided(me, 0.0008 / (size / float(max(ext))))
            me.transform(Matrix.Translation(-base_pt))
            apply(me, M3, size / float(max(ext)), o.matrix_world.translation + V((0, 0, -0.06)))
            log(f'{nm}: axis {"xyz"[ax]} top {"-+"[top_sign > 0]}')
        elif how == 'ball':
            M3 = rot_to((1, 0, 0), (0, 1, 0), (0, 0, 1), (0, 0, 1))
            me.transform(Matrix.Translation(-V(c)))
            apply(me, M3, size / float(max(ext)), o.matrix_world.translation)
            log(f'{nm}: window +x -> forward')
        elif how == 'pod':
            M3 = rot_to((1, 0, 0), (0, 1, 0), (0, 0, 1), (0, 0, 1))
            topz = V(c); topz[2] = hi[2]
            me.transform(Matrix.Translation(-topz))
            apply(me, M3, size / float(max(ext)), o.matrix_world.translation + V((0, 0, 0.42)))
            log(f'{nm}: slots +x -> forward, top plate at the ring')
        else:   # mantlet: open side (fewest vertices near that face) faces forward into the tail
            cnt = []
            for i in range(3):
                for sgn in (-1, 1):
                    edge = hi[i] if sgn > 0 else lo[i]
                    cnt.append(((np.abs(P[:, i] - edge) < 0.08 * ext[i]).sum(), i, sgn))
            n_, i_, sgn_ = min(cnt)
            src_open = [0, 0, 0]; src_open[i_] = sgn_
            upi = [k for k in range(3) if k != i_][0]
            src_up = [0, 0, 0]; src_up[upi] = 1
            M3 = rot_to(src_open, (0, 1, 0), src_up, (0, 0, 1))      # open side toward +Y (into the tail), dome aft
            me.transform(Matrix.Translation(-V(c)))
            apply(me, M3, size / float(max(ext)), o.matrix_world.translation + V((0, -0.05, 0)))
            log(f'{nm}: open side {"-+"[sgn_ > 0]}{"xyz"[i_]} -> forward')
        obj(nm.replace('_ng', '') + '_body', me, o, coll, 'pr_' + nm)


def split_blades(me, prop_obj, coll, hub_name, centre, R):
    """M2: ConstantSpeedProp needs one renderer per blade (stopped blades, damage meshes): the fal prop (world placed, axis +Y)
    is split into the hub (r < 0.30 R) and 3 blades by azimuth. Hub object prop_hub_n (child of prop_n); blades prop_hub_n_blade1..3
    are children of the hub with local +Z = their radial direction (Unity +Y, the B-25H blade convention), origin at the hub centre."""
    import bmesh as _bm
    bm = _bm.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
    def rad(p):
        d = V((p.x - centre.x, 0, p.z - centre.z)); return d
    tips = []
    for v in bm.verts:
        d = rad(v.co)
        if d.length > 0.75 * R:
            tips.append(d.normalized())
    dirs = []
    if tips:     # 3-blade prop: the other two blades sit at +-120 deg about the axis (+Y) from the longest tip
        t0 = max(tips, key=lambda t: 0) if False else tips[0]
        a0 = math.atan2(t0.x, t0.z)
        dirs = [V((math.sin(a0 + k * 2 * math.pi / 3), 0, math.cos(a0 + k * 2 * math.pi / 3))) for k in range(3)]
    groups = {k: [] for k in range(-1, len(dirs))}
    for f in bm.faces:
        c = f.calc_center_median()
        d = rad(c)
        if d.length < 0.30 * R or not dirs:
            groups[-1].append(f.index)
        else:
            k = max(range(len(dirs)), key=lambda i: d.normalized().dot(dirs[i]))
            groups[k].append(f.index)
    bm.free()
    def sub(ids, name, frame_z):
        b2 = _bm.new(); b2.from_mesh(me); b2.faces.ensure_lookup_table()
        keep = set(ids)
        _bm.ops.delete(b2, geom=[f for f in b2.faces if f.index not in keep], context='FACES')
        _bm.ops.delete(b2, geom=[v for v in b2.verts if not v.link_faces], context='VERTS')
        m2 = bpy.data.meshes.new(name); b2.to_mesh(m2); b2.free()
        return m2
    hub_me = sub(groups[-1], hub_name, None)
    hub = obj(hub_name, hub_me, prop_obj, coll, 'pr_prop3')
    for k in range(len(dirs)):
        bname = f'{hub_name}_blade{k + 1}'
        m2 = sub(groups[k], bname, dirs[k])
        z = dirs[k]; x = V((0, 1, 0)).cross(z).normalized(); y = z.cross(x)
        Mf = Matrix((x, y, z)).transposed().to_4x4(); Mf.translation = centre
        m2.transform(Mf.inverted())
        b = bpy.data.objects.new(bname, m2); coll.objects.link(b)
        b.parent = hub; b.matrix_parent_inverse = Matrix.Identity(4); b.matrix_world = Mf
        b['b17g_prop_mat'] = 'pr_prop3'; b['b25_info'] = '{"kind": "blade"}'
    log(f'{hub_name}: hub {len(groups[-1])} faces, {len(dirs)} blades {[len(groups[k]) for k in range(len(dirs))]}')


CK = {   # prop: (source up axis already +Z for all; source front axis -> target)
    'ck_seat': dict(front=(1, 0, 0), size='h'),
    'ck_column': dict(front=(1, 0, 0), size='h'),
    'ck_yoke': dict(front=(1, 0, 0), size='w'),
    'ck_yoke2': dict(front=(1, 0, 0), size='w'),
    'ck_quadrant2': dict(front=(1, 0, 0), size='w'),
    'ck_quadrant': dict(front=(1, 0, 0), size='w'),
    'ck_lever_t': dict(front=(1, 0, 0), size='h'),
    'ck_lever_knob': dict(front=(1, 0, 0), size='h'),
    'ck_c1': dict(front=(1, 0, 0), size='w'),
}


def place_cockpit(objs, coll, S):
    """cockpit fal props on their anchors (b17g_cockpit.anchors): bottom at the anchor (seat, column, levers, quadrant), centred on
    the hub (yoke, C-1 box); seat / quadrant / C-1 face the pilot side per their own front axis; scaled to the anchor's h / w."""
    import json as _j
    cache = {}
    for o in list(objs.values()):
        info = _j.loads(o.get('b25_info') or '{}') if o.get('b25_info') else {}
        nm = info.get('prop')
        if not nm or not os.path.exists(os.path.join(OPT, nm + '.glb')):
            continue
        if nm not in cache:
            cache[nm] = load(nm)
        me = cache[nm].copy()
        P = verts(me); lo, hi = bbox(P); c = (lo + hi) / 2; ext = hi - lo
        spec = CK[nm]
        if nm.startswith('ck_yoke'):
            # anchor frame: local +X toward the pilot, +Z up; source: +X = pilot side, +Z up, width along Y
            sc = info['w'] / float(ext[1])
            me.transform(Matrix.Translation(-V(c)))
            me.transform(Matrix.Diagonal((sc, sc, sc, 1)))
            me.transform(o.matrix_world)
        else:
            if 'h' in info:
                sc = info['h'] / float(ext[2])
            else:
                sc = info['w'] / float(max(ext[0], ext[1]))
            base = V((c[0], c[1], lo[2]))
            me.transform(Matrix.Translation(-base))
            me.transform(Matrix.Diagonal((sc, sc, sc, 1)))
            if info.get('kind') in ('lever', 'lever_static'):
                me.transform(Matrix.Rotation(math.radians(info.get('rest_deg', 0.0)), 4, 'X'))   # idle lean (Blender +X: top toward +Y)
            elif nm == 'ck_seat':
                me.transform(Matrix.Rotation(math.radians(90), 4, 'Z'))       # seat front +X -> +Y (toward the panel)
            elif nm.startswith('ck_quadrant'):
                me.transform(Matrix.Rotation(math.radians(-90), 4, 'Z'))      # quadrant face (+X, plates) -> -Y (toward the pilots)
            elif nm == 'ck_c1':
                me.transform(Matrix.Rotation(math.radians(-90), 4, 'Z'))      # C-1 face toward the pilots (-Y)
            if nm == 'ck_c1':
                me.transform(Matrix.Translation(V((0, 0, -ext[2] * sc / 2))))
            me.transform(Matrix.Translation(o.matrix_world.translation))
        obj(o.name + '_mesh', me, o, coll, 'pr_' + nm)
    log(f'cockpit props placed: {sorted(cache)}')
