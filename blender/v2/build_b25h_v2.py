"""Build the B-25H v2 model from scratch (procedural) and save it as a .blend.

  blender --background --factory-startup --python blender/v2/build_b25h_v2.py -- --out assets/model_v2/b25h_v2.blend

Blender space: nose +Y, up +Z, right wing +X, metres. Landing gear extended, gear doors open,
bomb doors closed. All exterior paint faces share one packed UV atlas `livery`; every face also has
a tiling box-projected UV map `detail`.
"""
import bpy, bmesh, sys, os, math, json
from mathutils import Vector, Matrix, Quaternion

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
for m in ('b25h_spec', 'b25h_geom', 'b25h_parts', 'b25h_interior', 'b25h_v3', 'b25h_v3_cockpit', 'b25h_v3_arms'):
    sys.modules.pop(m, None)
import b25h_spec as S
import b25h_parts as P
import b25h_seam1814 as SEAM
SEAM_LAP_1814 = True      # 1.8.14 (offline M): dark lap strip under every torn fuselage seam, torn-end walls >= 2.5 mm under the skin
from b25h_geom import V, MeshBuf, planar_uv

MATERIALS = {   # name: (base colour RGBA, metallic, roughness)
    'paint': ((0.26, 0.28, 0.17, 1.0), 0.0, 0.6),        # olive drab
    'interior': ((0.33, 0.40, 0.20, 1.0), 0.0, 0.7),     # zinc chromate green, darkened
    'structure': ((0.50, 0.52, 0.50, 1.0), 0.6, 0.45),   # bare aluminium
    'glass': ((0.70, 0.80, 0.85, 0.22), 0.0, 0.05),
    'metal_dark': ((0.06, 0.06, 0.065, 1.0), 0.7, 0.4),
    'rubber': ((0.025, 0.025, 0.025, 1.0), 0.0, 0.9),
    'prop': ((0.03, 0.03, 0.03, 1.0), 0.2, 0.5),
    'prop_tip': ((0.95, 0.75, 0.05, 1.0), 0.0, 0.5),
    'cockpit': ((0.08, 0.10, 0.07, 1.0), 0.0, 0.8),      # dark green/black interior paint
    'gauges': ((0.85, 0.85, 0.80, 1.0), 0.0, 0.4),
    'screen': ((0.02, 0.03, 0.03, 1.0), 0.0, 0.3),       # MFD quads (build swaps in the tac-screen material)
    'propdisc': ((0.10, 0.10, 0.10, 0.35), 0.0, 0.6),    # prop blur meshes (separate FBX)
    # 2026-11-01 cockpit rebuild: fal art atlas / tiles (bk_*) and fal 3D props (pr_<name>, own baked textures in Unity)
    'bk_art': ((0.10, 0.10, 0.10, 1.0), 0.0, 0.6), 'bk_quilt': ((0.24, 0.27, 0.18, 1.0), 0.0, 0.9),
    'bk_od': ((0.22, 0.24, 0.15, 1.0), 0.1, 0.6), 'bk_black': ((0.02, 0.02, 0.02, 1.0), 0.0, 0.6),
    'pr_yoke': ((0.05, 0.05, 0.05, 1.0), 0.2, 0.5), 'pr_column': ((0.22, 0.24, 0.15, 1.0), 0.2, 0.5),
    'pr_throttle': ((0.1, 0.1, 0.1, 1.0), 0.3, 0.5), 'pr_proplever': ((0.1, 0.1, 0.1, 1.0), 0.3, 0.5),
    'pr_mixture': ((0.5, 0.05, 0.05, 1.0), 0.2, 0.5), 'pr_trimwheel': ((0.05, 0.05, 0.05, 1.0), 0.2, 0.5),
    'pr_pedal': ((0.3, 0.3, 0.25, 1.0), 0.4, 0.5), 'pr_seat': ((0.22, 0.24, 0.15, 1.0), 0.1, 0.7),
    'pr_boot': ((0.06, 0.06, 0.05, 1.0), 0.0, 0.8), 'pr_footrest': ((0.22, 0.24, 0.15, 1.0), 0.2, 0.6),
    'pr_loom': ((0.12, 0.11, 0.08, 1.0), 0.0, 0.8),
}


def make_materials():
    mats = {}
    for name, (col, met, rough) in MATERIALS.items():
        m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        m.use_nodes = True
        bsdf = m.node_tree.nodes.get('Principled BSDF')
        if bsdf:
            bsdf.inputs['Base Color'].default_value = col
            bsdf.inputs['Metallic'].default_value = met
            bsdf.inputs['Roughness'].default_value = rough
            if col[3] < 1:
                bsdf.inputs['Alpha'].default_value = col[3]
        m.diffuse_color = col
        if col[3] < 1:
            try:
                m.surface_render_method = 'BLENDED'
            except Exception:
                pass
            m.use_backface_culling = False
        mats[name] = m
    return mats


# ------------------------------------------------------------------------------------------ parts
def mac_and_cg():
    """mean aerodynamic chord by numeric integration of the planform (one wing, incl. carry-through)."""
    xs = [0.0 + 10.30 * k / 400 for k in range(401)]
    num = den = numle = 0.0
    for x in xs:
        ax = max(x, 0.62)
        if ax <= 9.58:
            le, te = S.WING_LE(ax), S.WING_TE(ax)
        else:
            from b25h_geom import interp_table
            le, te = interp_table([(r[0], r[1:]) for r in S.WING_TIP], ax)
        c = le - te
        num += c * c
        den += c
        numle += c * le
    mac = num / den
    # LE of MAC: chord-weighted position of the LE where chord == mac (approx via weighting)
    le_mac = None
    for x in xs:
        ax = max(x, 0.62)
        if ax <= 9.58 and abs((S.WING_LE(ax) - S.WING_TE(ax)) - mac) < 0.02:
            le_mac = S.WING_LE(ax)
            x_mac = ax
            break
    cg_y = le_mac - 0.27 * mac
    return mac, le_mac, x_mac, cg_y


def collect_parts():
    import b25h_v3 as V3
    import b25h_v3_cockpit as C3
    import b25h_v3_arms as A3
    parts = []
    fus, holes = P.build_fuselage()
    fus['fus_center'].parent = 'B25H_root'
    fus['fus_forward'].parent = 'fus_center'
    fus['fus_cockpit'].parent = 'fus_forward'
    fus['fus_nose'].parent = 'fus_cockpit'
    fus['fus_rear'].parent = 'fus_center'
    fus['fus_tail'].parent = 'fus_rear'
    parts += list(fus.values())
    # bay interior volume (fus_center): tall between the carry-through spars, shallow outside them
    P.open_profile_box(fus['fus_center'].mesh, [(S.BAY_Y[1] - 0.01, -0.83), (S.BAY_Y[1] - 0.01, -0.05), (0.70, -0.05), (0.70, 1.05),
                       (-0.86, 1.05), (-0.86, -0.05), (S.BAY_Y[0] + 0.01, -0.05), (S.BAY_Y[0] + 0.01, -0.83)],
                       -(S.BAY_HALF_X - 0.005), S.BAY_HALF_X - 0.005, 'interior')
    # doors from hull openings
    for tag, nm, par, pose_open in (('bayL', 'bomb_door_L', 'fus_center', False), ('bayR', 'bomb_door_R', 'fus_center', False),
                                    ('nwL', 'gear_door_nose_L', 'fus_cockpit', True), ('nwR', 'gear_door_nose_R', 'fus_cockpit', True)):
        qs = holes[tag]
        d = P.door_from_holes(nm, par, qs, lambda p: abs(p.x), 0.0, '')
        op = P.open_pose(d, qs, 92.0 if 'bomb' in nm else 95.0)
        ang = math.degrees(op.angle) * (1 if op.axis.dot(V(d.info['hinge_axis'])) > 0 else -1)
        d.info['open_deg'] = round(ang, 1)
        d.info['note'] = ('bomb bay door, closed in file; open = rotate open_deg about hinge axis (swings down/outward)'
                          if 'bomb' in nm else 'nose gear door, OPEN in file (gear down); closed = identity')
        if pose_open:
            d.pose = op
        parts.append(d)
    # v3: smooth canopy + roof escape hatch, entrance hatches, waist hatches
    parts += V3.build_canopy()
    parts += V3.hatch_from_holes('hatch_entry_fwd', 'fus_forward', holes['hatchFwd'], 100.0,
                                 'forward crew entrance hatch (under the navigator/turret compartment, aft of the nose wheel well); '
                                 'hinged at its front edge, drops down; jettison = Canopy.ejectionTransform')
    parts += V3.hatch_from_holes('hatch_entry_rear', 'fus_rear', holes['hatchRear'], 100.0,
                                 'rear entrance hatch under the aft fuselage; hinged at its front edge, drops down')
    socks = {}
    for side in (-1, 1):
        hp_, sock = V3.build_waist_hatch(side, holes)
        parts += hp_
        socks[side] = sock
    for side in (-1, 1):
        parts += P.build_wing(side)
        nac, doors = P.build_nacelle(side)
        parts += [nac] + doors
        eng, flaps, exh = P.build_engine(side)
        parts += [eng, exh] + flaps
        parts += P.build_prop(side)
        parts += P.build_tail(side)
        parts += P.main_strut(side)
        parts += P.build_package_guns(side)
        parts += A3.build_waist_gun(side, socks[side])
        L = 'L' if side < 0 else 'R'
        parts.append(P.Part(f'prop_disc_{L}', f'prop_hub_{L}', (side * S.NAC_X, S.PROP_Y, 0.0), None,
                            info=dict(kind='prop_disc', note='MeshFilter slot for ConstantSpeedProp.propDisc; meshes in '
                                      'b25h_v2_propdisc.fbx (propdisc_blur, propdisc_full); local +Z (Unity) = spin axis')))
    parts += P.nose_strut()
    parts += A3.build_top_turret()
    parts += A3.build_tail_turret()
    parts += [p for p in P.build_nose_guns() if p.name not in ('cannon', 'muzzle_cannon')]
    parts += A3.build_cannon()
    import b25h_cockpit2 as CK2                     # 2026-11-01: historical B-25 cockpit rebuild (fal art + fal props)
    parts += CK2.build_cockpit()
    parts += A3.build_pylons()
    parts += A3.build_rear_crew()
    import b25h_interior as I
    byname = {p.name: p for p in parts}
    I.add_nose_compartment(byname['fus_nose'].mesh, byname['nose_guns'].mesh)
    I.add_cannon_bits(byname['fus_cockpit'].mesh)
    I.add_forward_compartment(byname['fus_forward'].mesh)
    I.add_center_compartment(byname['fus_center'].mesh, P.wing_station(0.62, 1))
    A3.add_bay_carrier(byname['fus_center'].mesh)
    I.add_rear_compartment(byname['fus_rear'].mesh)
    I.add_tail_compartment(byname['fus_tail'].mesh)
    A3.add_tail_fixed(byname['fus_tail'].mesh)
    # nose wheel well: enclosed open-bottom box (fus_cockpit), sized for the retracted wheel + strut
    y0, y1 = S.NOSE_WELL_Y
    hx = S.NOSE_WELL_HALF_X - 0.01
    # 2026-11-01 cockpit v3: top-front corner chamfered (b25h_cockpit2.WELL_CHAMFER, as the GA-25X 0.3.2): the crew figures'
    # inner feet stand in the footwell just ahead of it (the retracted wheel lies aft, near y 2.3; the strut pivot at z -0.45)
    (cy0, cz0), (cy1, cz1) = CK2.WELL_CHAMFER
    P.open_profile_box(byname['fus_cockpit'].mesh, [(y1, -0.84), (cy1, cz1), (cy0, cz0), (y0, 0.06), (y0, -0.84)], -hx, hx, 'interior')
    # v3: torn breaks (after every mesh addition, before the UV atlas)
    tear_report = {}
    if S.FEATURES.get('torn_breaks'):
        # 1.8.14 (offline M): seam lap strips + torn-end walls under the skin (b25h_seam1814.py); False = 1.8.13
        seam_rec = SEAM.collect(byname) if SEAM_LAP_1814 else None
        tear_report['fuselage'] = V3.tear_fuselage(byname)
        if seam_rec is not None:
            tear_report['seam1814'] = SEAM.apply(byname, seam_rec)
        tear_report['wings'] = V3.tear_wings(byname)
    print('[build] tear', tear_report)
    # livery weld groups: continuous skins across objects
    for p in parts:
        n = p.name
        if n.startswith('fus_') or n.startswith(('bomb_door', 'gear_door_nose', 'hatch_entry')):
            p.uv_group = 'fuselage'
        elif n.startswith(('nacelle_', 'gear_door_main_')):
            p.uv_group = 'nacelle_' + n.split('_')[-2 if n.startswith('gear') else -1]
        elif n.startswith(('wing_inner_', 'wing_outer_', 'wing_tip_')):
            p.uv_group = 'wing_' + n[-1]
    # empties
    mac, le_mac, x_mac, cg_y = mac_and_cg()
    root = P.Part('B25H_root', None, (0.0, cg_y, 0.25), None,
                  info=dict(note=f'CG at 27% MAC: MAC={mac:.3f} m, LE(MAC) y={le_mac:.3f} at |x|={x_mac:.2f}'))
    parts.insert(0, root)
    parts.append(P.Part('hp_bombbay', 'fus_center', A3.HP_BOMBBAY, info=dict(kind='hardpoint', note='v3: lowered 0.23 m so '
                        'stock internal mounts (bombs 0.15 m below the hardpoint) clear the bay roof; carrier beam above')))
    parts.append(P.Part('cockpit_eye', 'fus_cockpit', S.COCKPIT_EYE, info=dict(kind='crew_eye', crew='pilot')))
    extras = []
    if S.FEATURES.get('propdisc_separate_fbx'):
        for nm, mb in A3.prop_disc_meshes().items():
            e = P.Part(nm, None, (0, 0, 0), mb, info=dict(kind='prop_disc_mesh', note='hub frame; Unity +Z = spin axis; '
                                                          'UV: blur = v 0.5-1, full disc = v 0-0.5'))
            e.own_uv = True
            extras.append(e)
    return parts, holes, extras


def add_bay(mb):
    """bomb bay: open-bottom volume, tall between the carry-through spars, double-sided `interior`."""
    from b25h_geom import oriented_quad, ear_clip
    y_f, y_b = S.BAY_Y[1], S.BAY_Y[0]
    hx = S.BAY_HALF_X - 0.005
    zl = -0.83
    prof = [(y_f, zl), (y_f, -0.05), (0.70, -0.05), (0.70, 1.22), (-0.86, 1.22), (-0.86, -0.05), (y_b, -0.05), (y_b, zl)]
    n = len(prof)
    for j in range(n - 1):          # skip the bottom (open)
        a, b = prof[j], prof[j + 1]
        q = [V((-hx, a[0], a[1])), V((-hx, b[0], b[1])), V((hx, b[0], b[1])), V((hx, a[0], a[1]))]
        mid = (q[0] + q[2]) / 2
        inward = V((0, (y_f + y_b) / 2 - mid.y, 0.4 - mid.z))
        oriented_quad(mb, q, 'interior', inward)
        oriented_quad(mb, q, 'interior', -inward)
    tris = ear_clip(prof)
    for t in tris:
        for X, sgn in ((-hx, 1), (hx, -1)):
            pts = [V((X, prof[k][0], prof[k][1])) for k in t]
            oriented_quad(mb, pts, 'interior', V((sgn, 0, 0)))
            oriented_quad(mb, pts, 'interior', V((-sgn, 0, 0)))


# ------------------------------------------------------------------------------------------ UV atlas
def pack_livery(parts, margin=0.003):
    """Pack every `paint` face of every part into one 0-1 atlas.
    Faces that touch in 3D with identical metre-UVs are welded so continuous regions (the whole
    fuselage skin across its six sections, doors inside their openings) stay one island."""
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('livery')
    vmap = {}
    refs = []
    for pi, p in enumerate(parts):
        if p.mesh is None:
            continue
        for fi, f in enumerate(p.mesh.faces):
            if f['mat'] != 'paint':
                continue
            pts = [p.mesh.verts[i] for i in f['idx']]
            uv = f['uv']
            vs = []
            for q, u in zip(pts, uv):
                k = (p.uv_group, round(q.x, 4), round(q.y, 4), round(q.z, 4), round(u[0], 4), round(u[1], 4))
                if k not in vmap:
                    vmap[k] = bm.verts.new(q)
                vs.append(vmap[k])
            if len(set(vs)) < len(vs):
                vs = [bm.verts.new(q) for q in pts]
            try:
                face = bm.faces.new(vs)
            except ValueError:
                face = bm.faces.new([bm.verts.new(q) for q in pts])
            for loop, u in zip(face.loops, uv):
                loop[uvl].uv = u
            refs.append((pi, fi))
    me = bpy.data.meshes.new('_uvpack')
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new('_uvpack', me)
    bpy.context.scene.collection.objects.link(ob)
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.select_all(action='SELECT')
    kw = dict(rotate=True, margin=margin)
    try:
        bpy.ops.uv.pack_islands(udim_source='CLOSEST_UDIM', rotate=True, rotate_method='ANY', scale=True,
                                merge_overlap=False, margin_method='SCALED', margin=margin, shape_method='CONCAVE')
    except TypeError:
        bpy.ops.uv.pack_islands(**kw)
    bpy.ops.object.mode_set(mode='OBJECT')
    me = ob.data
    lay = me.uv_layers['livery'].data
    area = 0.0
    for poly, (pi, fi) in zip(me.polygons, refs):
        uvs = [tuple(lay[li].uv) for li in poly.loop_indices]
        parts[pi].mesh.faces[fi]['uv_packed'] = uvs
        for k in range(1, len(uvs) - 1):
            a, b, c = uvs[0], uvs[k], uvs[k + 1]
            area += abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])) / 2
    # texel density: metres per UV unit (from total 3D vs UV area)
    a3 = 0.0
    for poly in me.polygons:
        a3 += poly.area
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(me)
    return area, math.sqrt(a3 / area) if area > 0 else 0


# ------------------------------------------------------------------------------------------ objects
def part_matrix(p):
    return Matrix.Translation(p.pivot) @ p.frame.to_matrix().to_4x4() @ p.pose.to_matrix().to_4x4()


def create_objects(parts, mats, coll):
    objs = {}
    order = []
    names = {p.name: p for p in parts}
    done = set()

    def visit(p):
        if p.name in done:
            return
        if p.parent and p.parent in names:
            visit(names[p.parent])
        done.add(p.name)
        order.append(p)
    for p in parts:
        visit(p)
    for p in order:
        if p.mesh is None:
            ob = bpy.data.objects.new(p.name, None)
            ob.empty_display_type = 'ARROWS' if p.name.startswith(('muzzle', 'cockpit_eye', 'B25H')) else 'PLAIN_AXES'
            ob.empty_display_size = 0.15 if p.name != 'B25H_root' else 0.6
        else:
            inv = p.frame.inverted().to_matrix()
            mb = p.mesh
            verts = [tuple(inv @ (v - p.pivot)) for v in mb.verts]
            used = sorted({i for f in mb.faces for i in f['idx']})
            remap = {o: n for n, o in enumerate(used)}
            verts = [verts[i] for i in used]
            faces = [[remap[i] for i in f['idx']] for f in mb.faces]
            me = bpy.data.meshes.new(p.name)
            me.from_pydata(verts, [], faces)
            me.validate(clean_customdata=False)
            mat_names = []
            for f in mb.faces:
                if f['mat'] not in mat_names:
                    mat_names.append(f['mat'])
            for mn in mat_names:
                me.materials.append(mats[mn])
            liv = me.uv_layers.new(name='livery')
            det = me.uv_layers.new(name='detail')
            if len(me.polygons) != len(mb.faces):
                print('WARN face count changed', p.name, len(me.polygons), len(mb.faces))
            for poly, f in zip(me.polygons, mb.faces):
                poly.material_index = mat_names.index(f['mat'])
                poly.use_smooth = f['smooth']
                pts = [mb.verts[i] for i in f['idx']]
                n = (pts[1] - pts[0]).cross(pts[-1] - pts[0])
                for k, li in enumerate(poly.loop_indices):
                    if f['mat'] == 'paint' and 'uv_packed' in f:
                        liv.data[li].uv = f['uv_packed'][k]
                    elif (f['mat'] in ('gauges', 'screen', 'propdisc', 'ck_art', 'ck_throttle', 'bk_art') or f['mat'].startswith('pr_')) and f['uv']:     # ck_art: GA-25X 0.3.2 cockpit panel-art atlas
                        liv.data[li].uv = f['uv'][k]
                    else:
                        liv.data[li].uv = (0.0, 0.0)     # non-paint faces collapse to a corner (unused)
                    du = planar_uv(pts[k], n)
                    det.data[li].uv = (du[0] * 0.5, du[1] * 0.5)
            liv.active_render = True
            me.uv_layers.active = liv
            try:
                me.set_sharp_from_angle(angle=math.radians(38))
            except Exception:
                pass
            ob = bpy.data.objects.new(p.name, me)
        coll.objects.link(ob)
        if p.parent:
            ob.parent = objs[p.parent]
            ob.matrix_parent_inverse = Matrix.Identity(4)
        ob.matrix_world = part_matrix(p)
        bpy.context.view_layer.update()
        ob['b25_info'] = json.dumps(p.info) if p.info else ''
        objs[p.name] = ob
    return objs


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    out = argv[argv.index('--out') + 1] if '--out' in argv else os.path.join(HERE, '..', '..', 'assets', 'model_v2', 'b25h_v2.blend')
    out = os.path.abspath(out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    mats = make_materials()
    parts, holes, extras = collect_parts()
    usage, m_per_uv = pack_livery(parts)
    coll = bpy.data.collections.new('B25H_v2')
    scene.collection.children.link(coll)
    objs = create_objects(parts, mats, coll)
    if extras:
        xc = bpy.data.collections.new('B25H_extras')
        scene.collection.children.link(xc)
        create_objects(extras, mats, xc)
    tris = 0
    groups = {}
    for p in parts:
        if p.mesh is None:
            continue
        t = p.mesh.tri_count()
        tris += t
    stats = dict(objects=len(objs), tris=tris, livery_usage=round(usage, 4), metres_per_uv=round(m_per_uv, 3))
    scene['b25_build_stats'] = json.dumps(stats)
    print('[build] ' + json.dumps(stats))
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print('[build] saved', out)


if __name__ == '__main__':
    main()
