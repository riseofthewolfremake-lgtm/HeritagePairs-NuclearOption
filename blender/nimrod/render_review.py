"""Nimrod model review renders (user review 1, 2026-11-02): the 8 defect angles of the user's screenshots + close-ups,
with BACKFACE CULLING ON (as Unity), in material colours (workbench) and textured (EEVEE), plus a broken-apart view of
every split and the same cameras on the War Thunder reference (REFERENCE ONLY: rendered outside the repo).

  blender --background <nimrod.blend> --python blender/nimrod/render_review.py -- --out <dir> [--tex <textures dir>] [--modes solid,tex,broken]
  blender --background --factory-startup --python blender/nimrod/render_review.py -- --ref <wt obj> --out <dir outside the repo>
"""
import bpy, sys, os, math, json
from mathutils import Vector, Euler

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
def arg(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d
OUT = os.path.abspath(arg('--out', '.'))
REF, TEX = arg('--ref'), arg('--tex')
MODES = arg('--modes', 'solid,tex,broken').split(',')
os.makedirs(OUT, exist_ok=True)
sc = bpy.context.scene
EYE = Vector((0.0, -0.92, 0.745))

# name: (camera location, look-at target, horizontal fov deg, resolution)  - Blender frame (x right, y nose, z up)
VIEWS = {
    'd1_cockpit_struts': (EYE, EYE + Vector((0, 1.0, 0.10)), 100, (1800, 760)),
    'd2_front34_wings': (Vector((2.6, 6.2, 1.6)), Vector((0.0, 0.3, -0.15)), 55, (1800, 760)),
    'd2_guns_above': (Vector((0.55, 3.2, 1.55)), Vector((0.0, -0.6, 0.35)), 60, (1800, 760)),
    'd2_gun_close': (Vector((0.65, 2.35, 0.95)), Vector((0.12, 0.9, 0.42)), 45, (1600, 900)),
    'd3_cowling_side': (Vector((2.3, 1.2, 0.35)), Vector((0.3, 1.0, 0.05)), 60, (1800, 760)),
    'd4_interplane': (Vector((-1.3, -0.9, 1.05)), Vector((-3.6, 0.35, 0.15)), 70, (1800, 760)),
    'd4_interplane_ext': (Vector((-6.5, 3.2, 0.6)), Vector((-3.45, 0.3, 0.2)), 50, (1600, 900)),
    'd5_side_upperwing': (Vector((-11.0, 1.2, 2.2)), Vector((0.0, -0.4, 0.2)), 50, (1800, 760)),
    'd5_tip_R': (Vector((7.2, 1.5, 1.6)), Vector((4.8, 0.5, 1.0)), 50, (1600, 900)),
    'd5_tip_L': (Vector((-7.2, 1.5, 1.6)), Vector((-4.8, 0.5, 1.0)), 50, (1600, 900)),
    'd6_tail_below': (Vector((2.4, -8.5, -2.6)), Vector((0.0, -3.6, 0.1)), 50, (1800, 760)),
    'd6_tail_34': (Vector((2.6, -6.8, 1.4)), Vector((0.0, -4.1, 0.25)), 50, (1600, 900)),
    'd8_hook_deployed_side': (Vector((4.5, -2.6, -1.0)), Vector((0.0, -2.4, -0.9)), 55, (1600, 900)),
    'd8_hook_below': (Vector((1.6, -1.0, -3.2)), Vector((0.0, -2.6, -0.6)), 55, (1600, 900)),
    'd2_lower_root': (Vector((1.7, 1.9, -1.35)), Vector((0.42, -0.3, -0.56)), 45, (1600, 900)),
    'd2_lower_root_top': (Vector((1.6, 0.9, 0.15)), Vector((0.40, -0.3, -0.52)), 45, (1600, 900)),
    'd6_stab_root': (Vector((1.1, -3.0, 0.95)), Vector((0.15, -4.0, 0.2)), 45, (1600, 900)),
    'd6_stab_root_below': (Vector((1.0, -3.2, -0.9)), Vector((0.15, -4.0, 0.15)), 45, (1600, 900)),
    'd1_cabane_feet': (Vector((0.9, 0.5, 0.9)), Vector((0.36, 0.2, 0.42)), 50, (1600, 900)),
    'ck_pedals': (Vector((0.0, -0.62, 0.05)), Vector((0.0, -0.13, -0.43)), 70, (1600, 900)),
    'ck_pedals_side': (Vector((0.30, -0.55, -0.15)), Vector((0.0, -0.15, -0.43)), 60, (1600, 900)),
    'hinge_aileron_top': (Vector((3.9, -0.35, 1.75)), Vector((4.1, 0.25, 1.04)), 45, (1600, 900)),
    'hinge_aileron_rear': (Vector((3.6, -1.6, 1.25)), Vector((4.0, 0.25, 1.02)), 40, (1600, 900)),
    'hinge_elevator': (Vector((1.1, -5.0, 0.85)), Vector((0.9, -4.17, 0.2)), 45, (1600, 900)),
    'hinge_rudder': (Vector((0.9, -5.4, 0.9)), Vector((0.0, -4.47, 0.6)), 45, (1600, 900)),
    'gear_front': (Vector((1.6, 4.2, -1.2)), Vector((0.5, 0.7, -1.3)), 50, (1600, 900)),
    'full_34front': (Vector((7.5, 8.5, 2.6)), Vector((0, 0.2, 0.2)), 40, (1600, 1000)),
    'full_34rear': (Vector((-8.0, -9.0, 3.5)), Vector((0, -0.6, 0.2)), 40, (1600, 1000)),
    'full_side': (Vector((-12.0, -0.6, 0.3)), Vector((0, -0.9, 0.0)), 42, (1600, 900)),
}


def cam(name, loc, target, fov):
    c = bpy.data.cameras.new(name)
    c.sensor_width = 36; c.lens = 18 / math.tan(math.radians(fov) / 2)
    c.clip_start = 0.01; c.clip_end = 300
    o = bpy.data.objects.new(name, c); sc.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return o


def render(path, c, res):
    sc.camera = c
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print('[render]', path)


def workbench(color_type='MATERIAL'):
    sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading
    sh.light = 'STUDIO'; sh.color_type = color_type; sh.show_backface_culling = True
    sh.show_cavity = True; sh.cavity_type = 'WORLD'
    try:
        sh.show_object_outline = False
    except Exception:
        pass
    sc.render.film_transparent = False
    w = sc.world or bpy.data.worlds.new('w'); sc.world = w
    w.color = (0.55, 0.65, 0.78)


def import_ref(path):
    verts, faces = [], []
    for l in open(path):
        if l.startswith('v '):
            x, y, z = map(float, l.split()[1:4]); verts.append((-x, z, y))
        elif l.startswith('f '):
            faces.append([int(t.split('/')[0]) - 1 for t in l.split()[1:]])
    me = bpy.data.meshes.new('wt_ref'); me.from_pydata(verts, [], faces)
    ob = bpy.data.objects.new('wt_ref', me); sc.collection.objects.link(ob)
    return ob


def views_for(prefix):
    cams = {k: cam('rv_' + k, *v[:3]) for k, v in VIEWS.items()}
    for k, v in VIEWS.items():
        render(os.path.join(OUT, f'{prefix}{k}.png'), cams[k], v[3])


if REF:
    # WT reference: aligned by the propeller plane as in render_nimrod silhouettes (measure_wt: same frame), culling ON
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    ob = import_ref(REF)
    # WT origin -> our frame: shift so the prop tips' plane matches PROP_Y (measured offset kept in measure_wt.py)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    off = json.loads(arg('--ref_offset', '[0, 0, 0]'))
    ob.location = Vector(off)
    workbench('SINGLE'); sc.display.shading.single_color = (0.75, 0.72, 0.62)
    sc.display.shading.show_backface_culling = False
    views_for('wt_')
    raise SystemExit(0)

ours = [o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('cooper_')]
for o in bpy.data.objects:
    if o.name.startswith('cooper_'):
        o.hide_render = True
for m in bpy.data.materials:
    m.use_backface_culling = True
    try:
        m.use_backface_culling_shadow = True
    except Exception:
        pass

# hook shown deployed in the d8 views: second copy rotated about the hinge (the stowed one stays)
hook = bpy.data.objects.get('tailhook')

if 'solid' in MODES:
    workbench('MATERIAL')
    views_for('solid_')
    if hook is not None:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import nimrod_spec as S
        mw0 = hook.matrix_world.copy()
        piv = Vector(S.HOOK_PIVOT)
        from mathutils import Matrix
        R = Matrix.Translation(piv) @ Matrix.Rotation(-math.radians(S.HOOK_DEPLOY - S.HOOK_STOW_UP), 4, 'X') @ Matrix.Translation(-piv)
        hook.matrix_world = R @ mw0
        for k in ('d8_hook_deployed_side', 'd8_hook_below'):
            c = cam('rvh_' + k, *VIEWS[k][:3])
            render(os.path.join(OUT, f'solid_{k}_deployed.png'), c, VIEWS[k][3])
        hook.matrix_world = mw0

if 'broken' in MODES:
    # every part rendered alone (the part as it falls away) and its parent with the part removed, culling ON
    workbench('MATERIAL')
    groups = {
        'fus_engine': ['fus_engine'], 'fus_center': ['fus_center'], 'fus_rear': ['fus_rear'],
        'wing_upper_L': ['wing_upper_L'], 'wing_upper_C': ['wing_upper_C'], 'wing_lower_L': ['wing_lower_L'],
        'stab_L': ['stab_L'], 'fin': ['fin'], 'aileron_L': ['aileron_L'], 'elevator_L': ['elevator_L'], 'rudder': ['rudder'],
    }
    UNITY = {'fus_center', 'fus_engine', 'fus_rear', 'wing_upper_C', 'wing_upper_L', 'wing_upper_R', 'wing_lower_L', 'wing_lower_R', 'aileron_L',
             'aileron_R', 'stab_L', 'stab_R', 'elevator_L', 'elevator_R', 'fin', 'rudder'}

    def with_children(o):
        out, st = [o], list(o.children)
        while st:
            c = st.pop()
            if c.name in UNITY or c.name.startswith(('prop', 'gauge_', 'mfd_')):
                continue
            if c.type == 'MESH':
                out.append(c)
            st += list(c.children)
        return out
    for g, names in groups.items():
        objs = [x for n in names if n in bpy.data.objects for x in with_children(bpy.data.objects[n])]
        if not objs:
            continue
        for o in ours:
            o.hide_render = o not in objs
        vs = [o.matrix_world @ v.co for o in objs for v in o.data.vertices]
        lo = Vector([min(v[i] for v in vs) for i in range(3)]); hi = Vector([max(v[i] for v in vs) for i in range(3)])
        c0 = (lo + hi) / 2; r = max((hi - lo).length * 0.75, 0.6)
        for tag, d in (('a', Vector((0.8, 0.9, 0.5))), ('b', Vector((-0.7, -0.9, -0.3))), ('c', Vector((0.0, 1.0, 0.15))), ('d', Vector((0.0, -1.0, 0.15)))):
            if g.startswith(('wing_', 'aileron', 'stab', 'elevator')):
                d = {'a': Vector((0.9, 0.5, 0.6)), 'b': Vector((-0.9, -0.5, -0.3)), 'c': Vector((1.0, 0.05, 0.1)), 'd': Vector((-1.0, 0.05, 0.1))}[tag]
            c = cam(f'br_{g}_{tag}', c0 + d.normalized() * r * 2.2, c0, 50)
            render(os.path.join(OUT, f'broken_{g}_{tag}.png'), c, (1200, 800))
    for o in ours:
        o.hide_render = False

if 'tex' in MODES and TEX:
    sc.render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE_NEXT'
    w = sc.world or bpy.data.worlds.new('w'); sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get('Background'); bg.inputs[0].default_value = (0.55, 0.65, 0.78, 1); bg.inputs[1].default_value = 0.9
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN')); sc.collection.objects.link(sun)
    sun.data.energy = 4.0; sun.rotation_euler = Euler((math.radians(50), math.radians(15), math.radians(35)))
    fill = bpy.data.objects.new('fill', bpy.data.lights.new('fill', 'SUN')); sc.collection.objects.link(fill)
    fill.data.energy = 1.2; fill.rotation_euler = Euler((math.radians(120), 0, math.radians(-140)))
    try:
        sc.view_settings.view_transform = 'Standard'
    except Exception:
        pass
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import review_materials as RM
    RM.apply(os.path.abspath(TEX), arg('--livery'))
    for m in bpy.data.materials:
        m.use_backface_culling = True
    cams = {k: cam('rvt_' + k, *v[:3]) for k, v in VIEWS.items()}
    for k, v in VIEWS.items():
        render(os.path.join(OUT, f'tex_{k}.png'), cams[k], v[3])
