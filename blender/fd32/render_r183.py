"""Heritage Pairs 1.8.3 (offline B) canopy / coaming / internals review renders. Renders only; nothing here changes a model.

  blender --background <model.blend> --python blender/fd32/render_r183.py -- --set <set> --out <png prefix> [--hide <prefix,...>] [--head]

sets
  canopy   3/4 front, side, top, top (upper wing hidden), rear 3/4, eye forward / left / up-back, close coaming views (FD-32 or Mk I)
  coaming  close-ups of the cockpit edge from 12 directions (see-through / speck hunt)
  breaks   every detachable part pulled away from its neighbour, seen from the break face (internals)
Workbench, material colours, backface culling ON (as Unity), cavity shading. --head adds a 0.15 m helmet proxy at the stock pilot's head
(helmetCamPoint = cockpit_eye; head centre 6 cm behind / 2 cm above it, COIN pilot armature).
"""
import bpy, sys, os, math
from mathutils import Vector as V

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def arg(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d


SET, OUT = arg('--set', 'canopy'), arg('--out')
RES = tuple(int(x) for x in arg('--res', '1200,800').split(','))
os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
sc = bpy.context.scene
for o in bpy.data.objects:
    if o.name.startswith(('cooper_', 'wt_', 'chk_')):
        o.hide_render = True
for pre in [p for p in (arg('--hide', '') or '').split(',') if p]:
    for o in bpy.data.objects:
        if o.name.startswith(pre):
            o.hide_render = True


def look(loc, tgt, lens=40, name='cam'):
    c = bpy.data.cameras.new(name); c.lens = lens; c.clip_start = 0.02; c.clip_end = 300
    o = bpy.data.objects.new(name, c); sc.collection.objects.link(o)
    o.location = V(loc)
    o.rotation_euler = (V(tgt) - V(loc)).normalized().to_track_quat('-Z', 'Y').to_euler()
    return o


def render(path, cam, res=RES):
    sc.camera = cam
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print('[r183]', path)


sc.render.engine = 'BLENDER_WORKBENCH'
sh = sc.display.shading
sh.light = 'STUDIO'; sh.color_type = 'MATERIAL'; sh.show_cavity = True; sh.cavity_type = 'BOTH'
sh.show_object_outline = False; sh.show_backface_culling = True
sh.background_type = 'VIEWPORT'; sh.background_color = (0.62, 0.68, 0.74)
sc.display.render_aa = '8'
sc.render.film_transparent = False
for m in bpy.data.materials:
    if m.name == 'glass':
        m.diffuse_color = (0.45, 0.62, 0.75, 0.38)
    if m.name in ('paint',):
        m.diffuse_color = (0.50, 0.53, 0.55, 1.0)

eyeo = bpy.data.objects.get('cockpit_eye')
EYE = eyeo.matrix_world.translation.copy() if eyeo else V((0, -0.92, 0.745))
if '--head' in argv:
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.15, location=EYE + V((0, -0.06, 0.02)), segments=32, ring_count=16)
    hd = bpy.context.active_object; hd.name = 'r183_head'
    hm = bpy.data.materials.new('r183_head'); hm.diffuse_color = (0.08, 0.08, 0.09, 1); hd.data.materials.append(hm)
    for p in hd.data.polygons:
        p.use_smooth = True

C = V((0, EYE.y - 0.15, EYE.z))      # cockpit centre for the exterior views
if SET == 'canopy':
    views = {
        'front34': (C + V((-3.3, 2.4, 0.55)), C + V((0, 0.05, 0.05)), 40),
        'side': (C + V((-4.6, 0.0, 0.20)), C + V((0, 0, 0.0)), 40),
        'side_close': (C + V((-2.4, -0.25, 0.25)), C + V((0, -0.25, 0.05)), 40),
        'top': (C + V((0.0, -0.05, 4.8)), C + V((0, 0, 0)), 40),
        'rear34': (C + V((-2.8, -3.6, 1.6)), C + V((0, 0.1, 0.0)), 40),
        'front': (C + V((0.0, 5.5, 0.55)), C + V((0, 0, 0.15)), 50),
        'eye_fwd': (EYE, EYE + V((0.0, 1.0, -0.12)), 16),
        'eye_left': (EYE, EYE + V((-1.0, 0.35, 0.05)), 16),
        'eye_up': (EYE, EYE + V((0.25, 0.30, 1.0)), 16),
        'eye_back': (EYE + V((0, 0.02, 0.01)), EYE + V((-0.9, -1.0, 0.05)), 16),
    }
    hidden_top = [o for o in bpy.data.objects if o.name.startswith(('wing_upper', 'aileron', 'cabane', 'wire', 'strut'))]
    for k, (loc, tgt, lens) in views.items():
        if k == 'top':
            render(f'{OUT}_{k}.png', look(loc, tgt, lens, k))
            for o in hidden_top:
                o.hide_render = True
            render(f'{OUT}_topnowing.png', look(loc, tgt, lens, k + 'nw'))
            for o in hidden_top:
                o.hide_render = False
            continue
        render(f'{OUT}_{k}.png', look(loc, tgt, lens, k))
elif SET == 'breaks':
    # torn-off parts seen at their break faces: the engine section from behind (aft face y 0), the fuselage centre from the front
    def only(names):
        for o in bpy.data.objects:
            if o.type != 'MESH':
                continue
            keep = False
            q = o
            while q is not None:
                if q.name in names:
                    keep = True; break
                q = q.parent
            o.hide_render = not keep or o.name.startswith(('r183_', 'chk_', 'cooper_'))
    only({'fus_engine'})
    for k, (loc, tgt) in {'engine_aft34': ((-1.3, -1.6, 0.9), (0, 0.6, 0.0)), 'engine_aft': ((0.0, -1.7, 0.25), (0, 0.6, 0.0))}.items():
        render(f'{OUT}_{k}.png', look(loc, tgt, 40, k), (1000, 800))
    only({'fus_center'})
    for o in bpy.data.objects:
        if o.name.startswith(('fus_engine', 'fus_rear', 'wing_', 'aileron', 'flaperon', 'stab', 'elev', 'fin', 'rudder', 'prop', 'gear_', 'pylon', 'cabane', 'strut', 'wire', 'rigging')):
            o.hide_render = True
    render(f'{OUT}_centre_front34.png', look((1.3, 1.6, 0.9), (0, -0.5, 0.0), 40, 'cf'), (1000, 800))
elif SET == 'coaming':
    R = float(arg('--r', '1.5'))
    P = V((0, EYE.y + 0.05, EYE.z - 0.15))
    k = 0
    for az in range(-180, 180, 30):
        for el in (25, 55):
            a, e = math.radians(az), math.radians(el)
            d = V((math.sin(a) * math.cos(e), math.cos(a) * math.cos(e), math.sin(e)))
            render(f'{OUT}_{k:02d}_az{az}_el{el}.png', look(P + d * R, P, 45, f'c{k}'), (900, 650))
            k += 1
