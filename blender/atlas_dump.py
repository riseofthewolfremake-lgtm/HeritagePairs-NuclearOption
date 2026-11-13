"""Dump the livery-atlas part hashes of a model (1.8.16 guard, blender/atlas_guard.py).

  blender --background <model.blend> --python-exit-code 1 --python blender/atlas_dump.py -- <out.json>
  blender --background --python-exit-code 1 --python blender/atlas_dump.py -- <out.json> --fbx <model.fbx>
"""
import bpy, sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import atlas_guard as AG

argv = sys.argv[sys.argv.index('--') + 1:]
if '--fbx' in argv:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=argv[argv.index('--fbx') + 1])
parts = AG.scene_parts()
json.dump(dict(model=bpy.data.filepath or argv[argv.index('--fbx') + 1], atlas_hash=AG.atlas_hash(parts), parts=parts), open(argv[0], 'w'), indent=0)
print('[atlas] dump', AG.atlas_hash(parts), len(parts), 'paint parts ->', argv[0])
