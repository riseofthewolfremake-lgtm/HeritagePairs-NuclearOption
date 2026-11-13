"""Local fallback for the fal remesh step (B-25H cockpit v3, 2026-11-01): the fal account balance ran out after the tripo3d
image-to-3D calls, so tripo3d/tripo/remesh could not run for these props. This decimates the fal tripo raw model in Blender
(collapse, UVs kept, the tripo texture kept) and writes <name>_dec.glb next to the remeshed props.

  blender --background --factory-startup --python blender/v2/props/decimate_raw_prop.py -- <raw.glb> <out.glb> <target faces>
"""
import bpy, sys
a = sys.argv[sys.argv.index('--') + 1:]
src, dst, target = a[0], a[1], int(a[2])
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
ms = [o for o in bpy.context.scene.objects if o.type == 'MESH']
bpy.ops.object.select_all(action='DESELECT')
for o in ms:
    o.select_set(True)
bpy.context.view_layer.objects.active = ms[0]
if len(ms) > 1:
    bpy.ops.object.join()
o = bpy.context.view_layer.objects.active
for e in [x for x in bpy.context.scene.objects if x.type != 'MESH']:
    bpy.data.objects.remove(e)
o.parent = None
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
n0 = len(o.data.polygons)
d = o.modifiers.new('dec', 'DECIMATE')
d.ratio = min(1.0, target / max(1, n0))
bpy.ops.object.modifier_apply(modifier='dec')
print(f'[decimate] {src}: {n0} -> {len(o.data.polygons)} faces')
bpy.ops.export_scene.gltf(filepath=dst, export_format='GLB', use_selection=False, export_yup=True, export_apply=True)
