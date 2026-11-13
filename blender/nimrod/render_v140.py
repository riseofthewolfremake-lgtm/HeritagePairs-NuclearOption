"""Nimrod 1.4.0 review renders (user review 2, 2026-11-02): the angles of the user's screenshots (refs/nimrod_user_review_2)
plus orthographic tail / outline views, for OUR model (textured EEVEE or workbench) or for the War Thunder reference
(REFERENCE ONLY: imported in memory, rendered OUTSIDE the repo, never in git).

  blender --background <nimrod.blend> --python blender/nimrod/render_v140.py -- --out <dir> --prefix after_ [--tex <textures dir>] [--views a,b]
  blender --background --factory-startup --python blender/nimrod/render_v140.py -- --ref <wt obj> --out <dir outside the repo> --prefix wt_
"""
import bpy, sys, os, math
from mathutils import Vector, Euler, Matrix

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def arg(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d


OUT = os.path.abspath(arg('--out', '.'))
REF, TEX, PREFIX = arg('--ref'), arg('--tex'), arg('--prefix', '')
ONLY = set(arg('--views', '').split(',')) - {''}
HOOK_DEPLOYED = '--hook_down' in argv
os.makedirs(OUT, exist_ok=True)
EYE = Vector((0.0, -0.92, 0.745))

# name: (camera location, look-at target, horizontal fov deg OR ('ortho', scale), resolution)  Blender frame (x right, y nose, z up)
VIEWS = {
    's1_tail_top': (Vector((0, -4.15, 8.0)), Vector((0, -4.15, 0.0)), ('ortho', 4.2), (1400, 900)),
    's2_tail_below': (Vector((0, -4.15, -8.0)), Vector((0, -4.15, 0.0)), ('ortho', 4.2), (1400, 900)),
    's16_tail_side': (Vector((-9.0, -3.9, 0.35)), Vector((0, -3.9, 0.35)), ('ortho', 3.4), (1400, 1000)),
    's16_side': (Vector((-12.0, -1.3, 0.0)), Vector((0, -1.3, 0.0)), ('ortho', 9.4), (1800, 1000)),
    'top_full': (Vector((0, -1.0, 12.0)), Vector((0, -1.0, 0.0)), ('ortho', 11.0), (1600, 1300)),
    's4_hook': (Vector((-1.25, -1.0, -1.55)), Vector((0.0, -2.75, -0.62)), 62, (1600, 700)),
    's4_hook_side': (Vector((-3.2, -2.6, -0.9)), Vector((0.0, -2.6, -0.75)), 55, (1600, 800)),
    's6_radiator': (Vector((0.35, 2.15, -1.05)), Vector((0.12, 0.6, -0.72)), 62, (1400, 950)),
    's8_guns': (Vector((0.42, 0.55, 0.80)), Vector((0.0, -0.75, 0.60)), 66, (1600, 800)),
    's17_cockpit': (EYE, EYE + Vector((0, 1.0, 0.05)), 95, (1800, 760)),
    's10_centre': (Vector((-1.15, -1.35, 2.05)), Vector((0.35, 0.45, 0.95)), 58, (1500, 950)),
    's12_nose': (Vector((1.9, 3.7, 0.45)), Vector((0.0, 2.2, 0.05)), 45, (1400, 1000)),
    's12_nose_side': (Vector((-3.5, 2.3, 0.1)), Vector((0.0, 2.3, 0.0)), 42, (1400, 1000)),
    's13_seam_fus': (Vector((-2.1, 0.3, 1.25)), Vector((0.0, -1.6, 0.25)), 50, (1600, 800)),
    's14_seam_wing': (Vector((-0.4, -1.9, 2.2)), Vector((-1.6, 0.6, 0.95)), 60, (1600, 800)),
    's14_seam_wing_below': (Vector((-0.6, -0.4, -0.2)), Vector((-1.5, 0.5, 0.9)), 60, (1600, 800)),
    'nav_tip': (Vector((-6.3, 1.9, 1.4)), Vector((-5.05, 0.6, 1.05)), 40, (1400, 900)),
    'tail_34': (Vector((2.6, -7.2, 1.3)), Vector((0.0, -4.2, 0.25)), 48, (1600, 900)),
    'skid': (Vector((-1.4, -5.0, -0.9)), Vector((0.0, -4.25, -0.55)), 45, (1400, 900)),
    'full_34front': (Vector((7.5, 8.5, 2.6)), Vector((0, 0.2, 0.2)), 40, (1600, 1000)),
}


def cam(name, loc, target, fov):
    c = bpy.data.cameras.new(name)
    if isinstance(fov, tuple):
        c.type = 'ORTHO'; c.ortho_scale = fov[1]
    else:
        c.sensor_width = 36; c.lens = 18 / math.tan(math.radians(fov) / 2)
    c.clip_start = 0.01; c.clip_end = 300
    o = bpy.data.objects.new(name, c); bpy.context.scene.collection.objects.link(o)
    o.location = loc
    d = Vector(target) - Vector(loc)
    up = 'Y' if abs(d.normalized().z) > 0.99 else 'Y'
    o.rotation_euler = d.to_track_quat('-Z', up).to_euler()
    return o


def render(path, c, res):
    sc = bpy.context.scene
    sc.camera = c
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print('[render]', path)


def workbench(sc, color_type='MATERIAL'):
    sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading
    sh.light = 'STUDIO'; sh.color_type = color_type; sh.show_backface_culling = True
    sh.show_cavity = True; sh.cavity_type = 'WORLD'
    w = sc.world or bpy.data.worlds.new('w'); sc.world = w
    w.color = (0.86, 0.86, 0.86)


def import_ref(sc, path):
    verts, faces = [], []
    for l in open(path):
        if l.startswith('v '):
            x, y, z = map(float, l.split()[1:4]); verts.append((-x, z, y))
        elif l.startswith('f '):
            faces.append([int(t.split('/')[0]) - 1 for t in l.split()[1:]])
    me = bpy.data.meshes.new('wt_ref'); me.from_pydata(verts, [], faces)
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new('wt_ref', me); sc.collection.objects.link(ob)
    return ob


def run_views():
    for k, v in VIEWS.items():
        if ONLY and k not in ONLY:
            continue
        render(os.path.join(OUT, f'{PREFIX}{k}.png'), cam('rv_' + k, *v[:3]), v[3])


if REF:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    import_ref(sc, REF)
    workbench(sc, 'SINGLE'); sc.display.shading.single_color = (0.80, 0.80, 0.78)
    sc.display.shading.show_backface_culling = False
    run_views()
    raise SystemExit(0)

sc = bpy.context.scene
for o in bpy.data.objects:
    if o.name.startswith('cooper_'):
        o.hide_render = True
for m in bpy.data.materials:
    m.use_backface_culling = True
if HOOK_DEPLOYED:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import nimrod_spec as S
    for nm, piv, ang in (('tailhook', S.HOOK_PIVOT, S.HOOK_DEPLOY - S.HOOK_STOW_UP),
                         ('hook_visual', getattr(S, 'HOOKV_PIVOT', S.HOOK_PIVOT), getattr(S, 'HOOKV_DEPLOY', 0.0) - getattr(S, 'HOOKV_STOW', 0.0))):
        ob = bpy.data.objects.get(nm)
        if ob is None:
            continue
        R = Matrix.Translation(Vector(piv)) @ Matrix.Rotation(-math.radians(ang), 4, 'X') @ Matrix.Translation(-Vector(piv))
        ob.matrix_world = R @ ob.matrix_world
if TEX:
    sc.render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE_NEXT'
    w = sc.world or bpy.data.worlds.new('w'); sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get('Background'); bg.inputs[0].default_value = (0.6, 0.62, 0.66, 1); bg.inputs[1].default_value = 0.9
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN')); sc.collection.objects.link(sun)
    sun.data.energy = 4.0; sun.rotation_euler = Euler((math.radians(50), math.radians(15), math.radians(35)))
    fill = bpy.data.objects.new('fill', bpy.data.lights.new('fill', 'SUN')); sc.collection.objects.link(fill)
    fill.data.energy = 1.5; fill.rotation_euler = Euler((math.radians(130), 0, math.radians(-140)))
    try:
        sc.view_settings.view_transform = 'Standard'
    except Exception:
        pass
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import review_materials as RM
    RM.apply(os.path.abspath(TEX), arg('--livery'))
    for m in bpy.data.materials:
        m.use_backface_culling = True
else:
    workbench(sc)
run_views()
