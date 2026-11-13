"""1.8.16 livery-atlas guard as a standalone check on the FBX that Unity imports (any of the five aircraft).

  blender --background --python-exit-code 1 --python blender/atlas_check.py -- <model.fbx> <manifest.json> <out.json>

Used for the GA-25X, whose model check (check_b25h_v2.py variant) only runs inside blender/ga25x/run_ga25x.py (a model rebuild).
"""
import bpy, sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import atlas_guard as AG

fbx, man, out = sys.argv[sys.argv.index('--') + 1:][:3]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=fbx)
ok, detail = AG.check_row(man)
json.dump(dict(fbx=os.path.basename(fbx), manifest=os.path.basename(man), ok=ok, detail=detail), open(out, 'w'), indent=1)
print('[atlas]', 'PASS' if ok else 'FAIL', detail)
sys.exit(0 if ok else 1)
