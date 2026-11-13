"""Silhouette comparison against a user-supplied reference OBJ (visual reference only; never saved).

  blender --background --factory-startup --python blender/v2/compare_ref.py -- <ref.obj> <ours.blend> <outdir> [--composite-dir DIR]

The reference (nose -Y) is rotated 180 deg about Z and scaled by K = 20.60/20.98 so it lives in our
frame (nose +Y); both are rendered from the same cameras at the same ortho scale. Writes
<view>_ref.png and <view>_ours.png to outdir and, with --composite-dir, a stacked/overlay
composite compare_<view>.png (ours on top, outline of the reference overlaid in red).
"""
import bpy, sys, os, math
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
ref_obj, ours_blend, out = argv[:3]
comp_dir = argv[argv.index('--composite-dir') + 1] if '--composite-dir' in argv else None
os.makedirs(out, exist_ok=True)
K = 20.60 / 20.98

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.obj_import(filepath=ref_obj)
ref = [o for o in bpy.context.scene.objects if o.type == 'MESH']
ref_root = bpy.data.objects.new("REF", None)
bpy.context.scene.collection.objects.link(ref_root)
for o in ref:
    if o.parent is None:
        o.parent = ref_root
ref_root.rotation_euler = (0, 0, math.pi)
ref_root.scale = (K, K, K)

with bpy.data.libraries.load(ours_blend) as (src, dst):
    dst.objects = list(src.objects)
ours = [o for o in dst.objects if o is not None]
for o in ours:
    bpy.context.scene.collection.objects.link(o)
bpy.context.view_layer.update()


def bbox(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    return (Vector([min(p[i] for p in pts) for i in range(3)]), Vector([max(p[i] for p in pts) for i in range(3)]))


for nm, objs in (('REF(scaled)', ref), ('OURS', [o for o in ours if o.type == 'MESH'])):
    a, b = bbox(objs)
    print(nm, 'bbox', tuple(round(v, 2) for v in a), tuple(round(v, 2) for v in b), 'size', tuple(round(v, 2) for v in b - a))

scene = bpy.context.scene
scene.render.engine = 'BLENDER_WORKBENCH'
scene.display.shading.light = 'STUDIO'
scene.display.shading.color_type = 'SINGLE'
scene.display.shading.single_color = (0.45, 0.5, 0.35)
scene.display.shading.show_cavity = True
scene.render.resolution_x, scene.render.resolution_y = 1400, 1150
cam_data = bpy.data.cameras.new("cam")
cam_data.ortho_scale = 22.5
cam = bpy.data.objects.new("cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
C = Vector((0, -2.0, 0.3))
views = {"side": ((30, 0, 0), (math.pi / 2, 0, math.pi / 2), 'ORTHO'),
         "top": ((0, 0, 30), (0, 0, 0), 'ORTHO'),
         "front": ((0, 30, 0), (math.pi / 2, 0, math.pi), 'ORTHO'),
         "rear34": ((-18, -18, 10), (math.radians(65), 0, math.radians(-45)), 'PERSP')}
groups = {"ref": [o for o in scene.objects if o.type == 'MESH' and o not in ours],
          "ours": [o for o in ours if o.type == 'MESH']}
files = {}
for gname, objs in groups.items():
    for o in scene.objects:
        if o.type == 'MESH':
            o.hide_render = o not in objs
    for vname, (loc, rot, typ) in views.items():
        cam.location = C + Vector(loc)
        cam.rotation_euler = rot
        cam_data.type = typ
        cam_data.lens = 50
        f = os.path.join(out, f"{vname}_{gname}.png")
        scene.render.filepath = f
        bpy.ops.render.render(write_still=True)
        files[(vname, gname)] = f


def load(path):
    im = bpy.data.images.load(path)
    w, h = im.size
    a = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)
    bpy.data.images.remove(im)
    return a


if comp_dir:
    os.makedirs(comp_dir, exist_ok=True)
    for vname in views:
        A = load(files[(vname, 'ours')])
        R = load(files[(vname, 'ref')])
        bg = A[0, 0, :3]
        mask_r = np.abs(R[:, :, :3] - R[0, 0, :3]).sum(axis=2) > 0.02
        # outline of the reference silhouette
        edge = mask_r ^ np.roll(mask_r, 1, 0) | mask_r ^ np.roll(mask_r, 1, 1)
        over = A.copy()
        over[edge] = (1.0, 0.1, 0.1, 1.0)
        m = (np.abs(A[:, :, :3] - bg).sum(axis=2) > 0.02) | mask_r
        rows, cols = np.where(m.any(axis=1))[0], np.where(m.any(axis=0))[0]
        r0, r1 = max(rows[0] - 20, 0), min(rows[-1] + 20, A.shape[0])
        c0, c1 = max(cols[0] - 20, 0), min(cols[-1] + 20, A.shape[1])
        over, R = over[r0:r1, c0:c1], R[r0:r1, c0:c1]
        sep = np.ones((6, over.shape[1], 4), dtype=np.float32)
        comp = np.concatenate([R, sep, over], axis=0)    # rows are bottom-up: ours(+ref outline) on top, ref below
        h, w = comp.shape[:2]
        img = bpy.data.images.new('comp', w, h, alpha=True)
        img.pixels[:] = comp.ravel()
        img.filepath_raw = os.path.join(comp_dir, f'compare_{vname}.png')
        img.file_format = 'PNG'
        img.save()
print("RENDERED", out)
