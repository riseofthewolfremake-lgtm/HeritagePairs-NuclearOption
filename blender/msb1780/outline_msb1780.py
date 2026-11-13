"""MSB-17/80 vs the War Thunder B-17G reference outline (reference only: measured, never copied; imported in memory, never saved).

  blender -b assets/model_msb1780/msb1780.blend -P blender/msb1780/outline_msb1780.py -- --ref <B-17G-60-VE.obj> --out <dir>

Renders flat silhouettes (orthographic side / top / front, same cameras) of our model and of the reference (scaled to the 31.62 m span with
the B-17G rounds' transform: (-x, z, y) x 31.62 / 31.258), each alone, as PNG masks. tools/msb1780_outline_compare.py then measures, per view,
the silhouette IoU and the outline offset (distance from every reference outline pixel to ours) over the B-17 lines the MSB keeps
(fuselage, wing planform, tail) and separately where the MSB differs by design (nacelle fronts / props, turrets, pylons).
"""
import bpy, sys, os, math
from mathutils import Vector as V, Euler

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
REF = argv[argv.index('--ref') + 1]; OUT = os.path.abspath(argv[argv.index('--out') + 1]); os.makedirs(OUT, exist_ok=True)
K = 31.62 / 31.258
sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sc.display.shading.light = 'FLAT'; sc.display.shading.color_type = 'SINGLE'; sc.display.shading.single_color = (1, 1, 1)
sc.display.shading.background_type = 'WORLD'
w = sc.world or bpy.data.worlds.new('w'); sc.world = w; w.color = (0, 0, 0)
try:
    sc.view_settings.view_transform = 'Standard'
except Exception:
    pass
sc.render.resolution_x, sc.render.resolution_y = 2000, 2000
ours = [o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith(('gear_', 'wheel_', 'fork_', 'tyre'))]   # gear: the reference is gear-up
verts, faces = [], []
for l in open(REF, encoding='utf-8', errors='ignore'):
    if l.startswith('v '):
        x, y, z = map(float, l.split()[1:4]); verts.append((-x * K, z * K, y * K))
    elif l.startswith('f '):
        faces.append([int(t.split('/')[0]) - 1 for t in l.split()[1:]])
me = bpy.data.meshes.new('wt_ref'); me.from_pydata(verts, [], faces)
ref = bpy.data.objects.new('wt_ref', me); sc.collection.objects.link(ref)
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam
cam.data.type = 'ORTHO'; cam.data.ortho_scale = 34.0; cam.data.clip_end = 500
C = V((0, -3.6, 0.6))
VIEWS = {'side': ((-80, -3.6, 0.6), (V((0, -3.6, 0.6)) - V((-80, -3.6, 0.6))).to_track_quat('-Z', 'Y').to_euler()), 'top': ((0, -3.6, 80), Euler((0, 0, 0))),
         'front': ((0, 80, 0.4), (V((0, -3.6, 0.4)) - V((0, 80, 0.4))).to_track_quat('-Z', 'Y').to_euler())}
for vn, (loc, rot) in VIEWS.items():
    cam.location = V(loc); cam.rotation_euler = rot
    for who, show in (('msb', ours), ('wt', [ref])):
        for o in bpy.data.objects:
            if o.type == 'MESH':
                o.hide_render = o not in show
        sc.render.filepath = os.path.join(OUT, f'outline_{vn}_{who}.png')
        bpy.ops.render.render(write_still=True)
        print('[outline]', sc.render.filepath)
with open(os.path.join(OUT, 'outline_cam.txt'), 'w') as f:
    f.write(f'ortho_scale 34.0 res 2000 metres_per_px {34.0 / 2000}\n')
print('[outline] done')
